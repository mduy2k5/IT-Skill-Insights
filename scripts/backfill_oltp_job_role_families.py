#!/usr/bin/env python3
"""Backfill JobBERT V3 role family normalization to OLTP (PostgreSQL) jobs table.

Architecture Flow:
Crawler -> JobTitleNormalizer (JobBERT V3) -> OLTP (PostgreSQL jobs table) -> OLAP (DuckDB)

Normalizes all existing jobs in PostgreSQL:
- Cleans title & removes level cues (Senior, Intern, Chuyên viên...)
- Computes 1024-dim JobBERT embeddings & prototype cosine similarities
- Gates with tau=0.60, delta=0.06:
    * S1 >= 0.60 and Margin >= 0.06: AUTO_ASSIGNED (stores assigned family)
    * S1 >= 0.60 and Margin < 0.06: AMBIGUOUS_REVIEW (stores Top1 family & Top2 candidate)
    * S1 < 0.60: LOW_CONFIDENCE_REVIEW (stores Top1 family & Top2 candidate)
- Updates jobs table directly with single source of truth:
    role_family, role_cleaned_title, role_confidence, role_margin,
    role_decision_status, role_candidate_top2, role_normalized_at, role_model_version
- Also mirrors into shadow_job_role_predictions for audit trail.

Usage:
    python scripts/backfill_oltp_job_role_families.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = ROOT_DIR / "web" / "config"
ENV_PATH = ROOT_DIR / ".env"

sys.path.insert(0, str(ROOT_DIR / "scripts"))
from map_titles_to_role_families import JobTitleNormalizer

NORMALIZER_MODEL_VERSION = "jobbert-v3-prototype-v0.1"
GATE_TAU = 0.60
GATE_DELTA = 0.06


def load_env() -> dict[str, str]:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_pg_conn(env: dict[str, str]):
    return psycopg2.connect(
        host=env.get("JOB_POSTGRES_HOST", "127.0.0.1"),
        port=int(env.get("JOB_POSTGRES_PORT", "5434")),
        dbname=env.get("JOB_POSTGRES_DB", "it_job_platform"),
        user=env.get("JOB_POSTGRES_USER", "job_pipeline"),
        password=env.get("JOB_POSTGRES_PASSWORD", ""),
        connect_timeout=10,
    )


UPDATE_JOBS_SQL = """
    UPDATE jobs SET
        role_family          = %(role_family)s,
        role_cleaned_title   = %(role_cleaned_title)s,
        role_confidence      = %(role_confidence)s,
        role_margin          = %(role_margin)s,
        role_decision_status = %(role_decision_status)s,
        role_candidate_top2  = %(role_candidate_top2)s,
        role_normalized_at   = %(role_normalized_at)s,
        role_model_version   = %(role_model_version)s
    WHERE job_id = %(job_id)s
"""


UPSERT_SHADOW_SQL = """
    INSERT INTO shadow_job_role_predictions (
        job_id,
        source_job_key,
        model_version,
        input_title_raw,
        input_title_cleaned,
        predicted_family,
        confidence_score,
        margin_score,
        decision_status,
        candidate_families,
        human_review_status,
        evaluated_at
    ) VALUES (
        %(job_id)s, %(source_job_key)s, %(role_model_version)s,
        %(input_title_raw)s, %(role_cleaned_title)s,
        %(role_family)s, %(role_confidence)s, %(role_margin)s,
        %(role_decision_status)s, %(candidate_families)s,
        'pending', %(role_normalized_at)s
    )
    ON CONFLICT (source_job_key, model_version) DO UPDATE SET
        input_title_raw      = EXCLUDED.input_title_raw,
        input_title_cleaned  = EXCLUDED.input_title_cleaned,
        predicted_family     = EXCLUDED.predicted_family,
        confidence_score     = EXCLUDED.confidence_score,
        margin_score         = EXCLUDED.margin_score,
        decision_status      = EXCLUDED.decision_status,
        candidate_families   = EXCLUDED.candidate_families,
        evaluated_at         = EXCLUDED.evaluated_at
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of jobs to process")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without DB commit")
    args = parser.parse_args()

    env = load_env()
    print(f"[backfill] Connecting to PostgreSQL at {env.get('JOB_POSTGRES_HOST')}:{env.get('JOB_POSTGRES_PORT')}...")
    conn = get_pg_conn(env)

    # 1. Fetch all jobs
    fetch_sql = """
        SELECT job_id::text, source_job_key, title
        FROM jobs
        WHERE title IS NOT NULL AND title != ''
        ORDER BY created_at DESC
    """
    if args.limit:
        fetch_sql += f" LIMIT {args.limit}"

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(fetch_sql)
        jobs = [dict(r) for r in cur.fetchall()]

    total = len(jobs)
    print(f"[backfill] Retrieved {total} jobs from OLTP.")

    if total == 0:
        print("[backfill] No jobs found.")
        conn.close()
        return 0

    # 2. Initialize Normalizer
    print(f"[backfill] Loading JobBERT Normalizer (tau={GATE_TAU}, delta={GATE_DELTA})...")
    normalizer = JobTitleNormalizer()
    normalizer.confidence_tau = GATE_TAU
    normalizer.margin_delta = GATE_DELTA

    # 3. Process jobs
    job_updates = []
    shadow_records = []
    status_counts = {"AUTO_ASSIGNED": 0, "AMBIGUOUS_REVIEW": 0, "LOW_CONFIDENCE_REVIEW": 0}

    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"[backfill] Processing {total} titles through JobBERT...")
    for i, j in enumerate(jobs, 1):
        raw_title = j["title"]
        res = normalizer.map_title(raw_title)

        status = res["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

        top1_fam = res["top1_family"]
        top2_fam = res.get("top2_family")
        s1 = res["top1_similarity"]
        margin = res["margin"]

        # In OLTP jobs table, for AUTO_ASSIGNED we store the canon role family;
        # for review-pending, we store top1 with review flag, allowing immediate search
        role_fam_for_oltp = top1_fam

        candidates_json = json.dumps(
            [{"family": c["family_name"], "similarity": c["similarity"]} for c in res.get("top_candidates", [])],
            ensure_ascii=False
        )

        job_updates.append({
            "job_id": j["job_id"],
            "role_family": role_fam_for_oltp,
            "role_cleaned_title": res["cleaned_title"],
            "role_confidence": s1,
            "role_margin": margin,
            "role_decision_status": status,
            "role_candidate_top2": top2_fam,
            "role_normalized_at": now_iso,
            "role_model_version": NORMALIZER_MODEL_VERSION,
        })

        shadow_records.append({
            "job_id": j["job_id"],
            "source_job_key": j.get("source_job_key") or j["job_id"],
            "role_model_version": NORMALIZER_MODEL_VERSION,
            "input_title_raw": raw_title,
            "role_cleaned_title": res["cleaned_title"],
            "role_family": role_fam_for_oltp,
            "role_confidence": s1,
            "role_margin": margin,
            "role_decision_status": status,
            "candidate_families": candidates_json,
            "role_normalized_at": now_iso,
        })

        if i % 20 == 0 or i == total:
            print(f"  Processed {i}/{total} ({i/total*100:.1f}%) | AUTO={status_counts['AUTO_ASSIGNED']} AMBIGUOUS={status_counts['AMBIGUOUS_REVIEW']} LOW_CONF={status_counts['LOW_CONFIDENCE_REVIEW']}")

    # 4. Save to DB
    if not args.dry_run:
        print("[backfill] Updating OLTP jobs table and syncing shadow audit table...")
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, UPDATE_JOBS_SQL, job_updates, page_size=100)
            psycopg2.extras.execute_batch(cur, UPSERT_SHADOW_SQL, shadow_records, page_size=100)
        conn.commit()
        print(f"[backfill] Successfully updated {len(job_updates)} rows in jobs table.")
    else:
        print("[backfill] Dry run: No changes committed to DB.")

    conn.close()

    print("\n" + "=" * 65)
    print(f"{'OLTP ROLE FAMILY NORMALIZATION SUMMARY':^65}")
    print("=" * 65)
    print(f"  Total OLTP Jobs Processed : {total}")
    print(f"  AUTO_ASSIGNED             : {status_counts['AUTO_ASSIGNED']:>4} ({status_counts['AUTO_ASSIGNED']/total*100:.1f}%)")
    print(f"  AMBIGUOUS_REVIEW          : {status_counts['AMBIGUOUS_REVIEW']:>4} ({status_counts['AMBIGUOUS_REVIEW']/total*100:.1f}%)")
    print(f"  LOW_CONFIDENCE_REVIEW     : {status_counts['LOW_CONFIDENCE_REVIEW']:>4} ({status_counts['LOW_CONFIDENCE_REVIEW']/total*100:.1f}%)")
    print("=" * 65)
    print("OLTP is now the single source of truth for job searches and OLAP ETL!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
