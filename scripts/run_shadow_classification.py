#!/usr/bin/env python3
"""Shadow-mode JobBERT V3 role family classification runner.

Loads all jobs from PostgreSQL, runs JobBERT normalizer (τ=0.60, Δ=0.06) in PARALLEL
with Ruleset v0.1 keyword baseline, and writes predictions to `shadow_job_role_predictions`.

SHADOW MODE: results are stored only — they are NOT joined into OLAP skill aggregations
until the promotion gate is passed (see evaluate_shadow_vs_ruleset.py).

Usage:
    python scripts/run_shadow_classification.py [--limit N] [--dry-run]

Options:
    --limit N     Process only first N jobs (for testing)
    --dry-run     Print results but do not write to DB
    --model-ver   Model version tag (default: jobbert-v3-prototype-v0.1)
"""

from __future__ import annotations

import argparse
import json
import re
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

# Shadow gate parameters (confirmed in Step 6 analysis)
SHADOW_TAU = 0.60
SHADOW_DELTA = 0.06
MODEL_VERSION = "jobbert-v3-prototype-v0.1"
RULESET_VERSION = "ruleset-v0.1"


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

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
        host=env.get("POSTGRES_HOST", "localhost"),
        port=int(env.get("POSTGRES_PORT", "5434")),
        dbname=env.get("POSTGRES_DB", "it_job_platform"),
        user=env.get("POSTGRES_USER", "job_pipeline"),
        password=env.get("POSTGRES_PASSWORD", ""),
        connect_timeout=10,
    )


# ---------------------------------------------------------------------------
# Ruleset v0.1 keyword classifier (baseline)
# ---------------------------------------------------------------------------

class RulesetV01Classifier:
    """Keyword-based role family classifier using job_role_families_v0_1.json."""

    def __init__(self):
        cfg_path = CONFIG_DIR / "job_role_families_v0_1.json"
        self.config = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.review_label = self.config["review_group"]["label"]
        self.families = self.config["families"]

    def classify(self, raw_title: str) -> str:
        """Return matched family label or the review-group label."""
        lower = raw_title.lower()
        for fam in self.families:
            for kw in fam.get("match_any", []):
                if kw.lower() in lower:
                    return fam["label"]
        return self.review_label


# ---------------------------------------------------------------------------
# JobBERT normalizer (lazy-loaded to allow --dry-run without model download)
# ---------------------------------------------------------------------------

def load_normalizer() -> Any:
    """Import and instantiate JobTitleNormalizer with shadow gate params."""
    sys.path.insert(0, str(ROOT_DIR / "scripts"))
    from map_titles_to_role_families import JobTitleNormalizer

    normalizer = JobTitleNormalizer()
    # Override with shadow gate params
    normalizer.confidence_tau = SHADOW_TAU
    normalizer.margin_delta = SHADOW_DELTA
    return normalizer


# ---------------------------------------------------------------------------
# Fetch jobs from PostgreSQL
# ---------------------------------------------------------------------------

def fetch_jobs(conn, limit: int | None = None) -> list[dict]:
    """Return list of {job_id, source_job_key, title} from jobs table."""
    sql = """
        SELECT job_id::text, source_job_key, title
        FROM jobs
        WHERE title IS NOT NULL AND title != ''
        ORDER BY created_at DESC
    """
    if limit:
        sql += f" LIMIT {limit}"

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Write shadow predictions to PostgreSQL
# ---------------------------------------------------------------------------

UPSERT_SQL = """
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
        rule_v0_1_prediction,
        human_review_status,
        is_false_merge,
        evaluated_at
    ) VALUES (
        %(job_id)s, %(source_job_key)s, %(model_version)s,
        %(input_title_raw)s, %(input_title_cleaned)s,
        %(predicted_family)s, %(confidence_score)s, %(margin_score)s,
        %(decision_status)s, %(candidate_families)s,
        %(rule_v0_1_prediction)s, 'pending', NULL, %(evaluated_at)s
    )
    ON CONFLICT (source_job_key, model_version) DO UPDATE SET
        input_title_raw     = EXCLUDED.input_title_raw,
        input_title_cleaned = EXCLUDED.input_title_cleaned,
        predicted_family    = EXCLUDED.predicted_family,
        confidence_score    = EXCLUDED.confidence_score,
        margin_score        = EXCLUDED.margin_score,
        decision_status     = EXCLUDED.decision_status,
        candidate_families  = EXCLUDED.candidate_families,
        rule_v0_1_prediction = EXCLUDED.rule_v0_1_prediction,
        evaluated_at        = EXCLUDED.evaluated_at
"""


def write_predictions(conn, records: list[dict]) -> int:
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, UPSERT_SQL, records, page_size=200)
    conn.commit()
    return len(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def classify_job(job: dict, normalizer: Any, ruleset: RulesetV01Classifier) -> dict:
    """Run both classifiers on one job and return a DB-ready record."""
    raw_title = job["title"]
    res = normalizer.map_title(raw_title)

    # Build top-3 candidate JSONB
    candidates_json = json.dumps(
        [
            {"family": c["family_name"], "similarity": c["similarity"]}
            for c in res.get("top_candidates", [])
        ],
        ensure_ascii=False,
    )

    # Determine predicted family for shadow record
    predicted_family = (
        res["assigned_family"]
        if res["status"] == "AUTO_ASSIGNED"
        else res.get("top1_family", "Needs Review")
    )

    return {
        "job_id": job["job_id"],
        "source_job_key": job.get("source_job_key") or job["job_id"],
        "model_version": MODEL_VERSION,
        "input_title_raw": raw_title,
        "input_title_cleaned": res["cleaned_title"],
        "predicted_family": predicted_family,
        "confidence_score": res["top1_similarity"],
        "margin_score": res["margin"],
        "decision_status": res["status"],
        "candidate_families": candidates_json,
        "rule_v0_1_prediction": ruleset.classify(raw_title),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    parser.add_argument("--model-ver", type=str, default=MODEL_VERSION, help="Model version tag")
    args = parser.parse_args()

    model_ver = args.model_ver

    env = load_env()

    # ── Load JobBERT normalizer ──────────────────────────────────────────
    print(f"[shadow] Loading JobBERT normalizer (τ={SHADOW_TAU}, Δ={SHADOW_DELTA})...")
    normalizer = load_normalizer()
    ruleset = RulesetV01Classifier()

    # ── Connect to PostgreSQL ────────────────────────────────────────────
    if not args.dry_run:
        try:
            conn = get_pg_conn(env)
            print("[shadow] Connected to PostgreSQL.")
        except Exception as e:
            print(f"[shadow] ❌ DB connection failed: {e}")
            return 1
    else:
        conn = None
        print("[shadow] DRY-RUN mode: DB writes disabled.")

    # ── Fetch jobs ───────────────────────────────────────────────────────
    if conn:
        jobs = fetch_jobs(conn, limit=args.limit)
    else:
        # Dry-run: use benchmark titles as stand-in
        benchmark_path = DATA_DIR / "title_benchmark_v0_1.json"
        bm = json.loads(benchmark_path.read_text(encoding="utf-8"))
        jobs = [
            {"job_id": f"dry-{i}", "source_job_key": f"dry-{i}", "title": it["raw_title"]}
            for i, it in enumerate(bm.get("items", []))
        ]
        if args.limit:
            jobs = jobs[:args.limit]

    total = len(jobs)
    print(f"[shadow] Processing {total} jobs...")

    # ── Classify ─────────────────────────────────────────────────────────
    records = []
    counts: dict[str, int] = {"AUTO_ASSIGNED": 0, "AMBIGUOUS_REVIEW": 0, "LOW_CONFIDENCE_REVIEW": 0}
    ruleset_match = 0

    for i, job in enumerate(jobs, 1):
        try:
            rec = classify_job(job, normalizer, ruleset)
            records.append(rec)
            counts[rec["decision_status"]] = counts.get(rec["decision_status"], 0) + 1
            if rec["rule_v0_1_prediction"] != ruleset.review_label:
                ruleset_match += 1
        except Exception as e:
            print(f"  [!] Error on job {job.get('job_id')} ({job.get('title', '')[:60]}): {e}")

        if i % 50 == 0 or i == total:
            pct = i / total * 100
            print(f"  Progress: {i}/{total} ({pct:.0f}%)  AUTO={counts['AUTO_ASSIGNED']}  AMBIGUOUS={counts['AMBIGUOUS_REVIEW']}  LOW_CONF={counts['LOW_CONFIDENCE_REVIEW']}")

    # ── Write to DB ───────────────────────────────────────────────────────
    if conn and not args.dry_run:
        written = write_predictions(conn, records)
        conn.close()
        print(f"\n[shadow] ✅ Written {written} records to shadow_job_role_predictions.")
    else:
        # Print first 10 results in dry-run
        print("\n[shadow] DRY-RUN sample output (first 10 records):")
        for rec in records[:10]:
            print(
                f"  [{rec['decision_status']:25s}] "
                f"{rec['input_title_raw'][:55]:55s} → {rec['predicted_family'][:30]:30s} "
                f"(conf={rec['confidence_score']:.4f}, margin={rec['margin_score']:.4f}) "
                f"| ruleset={rec['rule_v0_1_prediction']}"
            )

    # ── Summary ───────────────────────────────────────────────────────────
    auto_rate = counts["AUTO_ASSIGNED"] / total * 100 if total > 0 else 0
    ruleset_rate = ruleset_match / total * 100 if total > 0 else 0

    print("\n" + "=" * 70)
    print(f"{'SHADOW CLASSIFICATION SUMMARY':^70}")
    print("=" * 70)
    print(f"  Model version  : {MODEL_VERSION}")
    print(f"  Gate params    : τ={SHADOW_TAU}, Δ={SHADOW_DELTA}")
    print(f"  Total jobs     : {total}")
    print(f"  AUTO_ASSIGNED  : {counts['AUTO_ASSIGNED']:>5}  ({auto_rate:.1f}%)")
    print(f"  AMBIGUOUS_REV  : {counts['AMBIGUOUS_REVIEW']:>5}  ({counts['AMBIGUOUS_REVIEW']/total*100:.1f}%)")
    print(f"  LOW_CONF_REV   : {counts['LOW_CONFIDENCE_REVIEW']:>5}  ({counts['LOW_CONFIDENCE_REVIEW']/total*100:.1f}%)")
    print(f"  Ruleset v0.1   : {ruleset_match:>5}  matched ({ruleset_rate:.1f}%)")
    print("=" * 70)
    print("\n[shadow] Done. Results are SHADOW-ONLY — not in live Analyst stats.")
    print("         Run evaluate_shadow_vs_ruleset.py to check promotion gate.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
