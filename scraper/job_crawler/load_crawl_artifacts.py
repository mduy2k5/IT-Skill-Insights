"""Load a stored crawl JSON artifact into the website OLTP tables.

Run in the Scrapy Docker service, for example:

    python /app/scraper/job_crawler/load_crawl_artifacts.py \
      --source-code saramin \
      --artifact-filename embedded_jobs_compact_company_2026-11-09.json \
      --project-track data

The source must be approved for metadata storage. Description fields are loaded
only when the source separately allows description storage. Replaying the same
artifact is safe: candidates are stored in `job_ingest_candidates` first, and
only verified candidates can be loaded with `--apply`. Job writes and candidate
status updates share one transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extras import Json

if __package__:
    from .job_validation import (
        VALIDATOR_VERSION,
        boolean_or_none,
        compose_description_text,
        decimal_or_none,
        normalize_listing_status,
        normalize_work_mode,
        nonnegative_int,
        parse_timestamp,
        print_validation_report,
        text_or_none,
        validate_jobs,
    )
else:
    # Support direct execution as `python /app/scraper/job_crawler/load_crawl_artifacts.py`.
    from job_validation import (
        VALIDATOR_VERSION,
        boolean_or_none,
        compose_description_text,
        decimal_or_none,
        normalize_listing_status,
        normalize_work_mode,
        nonnegative_int,
        parse_timestamp,
        print_validation_report,
        text_or_none,
        validate_jobs,
    )

PARSER_VERSION = "embedded-json-v1"


def label_rows(record: dict[str, Any], definitions: tuple[tuple[str, str, bool], ...]):
    """Return original label text with its source field and source order."""
    result = []
    for source_field, label_type, is_array in definitions:
        if source_field not in record or record[source_field] is None:
            continue
        value = record[source_field]
        if is_array and isinstance(value, list):
            values = enumerate(value)
        else:
            values = [(0, value)]
        for position, item in values:
            label_text = text_or_none(item)
            if label_text is not None:
                result.append((source_field, label_type, label_text, position))
    return result


JOB_LABEL_FIELDS = (
    ("skills_arr", "skill", True),
    ("extra_skills", "skill", True),
    ("level", "seniority", False),
    ("job_levels_arr", "seniority", True),
    ("contract_types_str", "employment_type", False),
    ("experiences_str", "experience", False),
    ("features", "feature", True),
)
COMPANY_LABEL_FIELDS = (
    ("nationalities_str", "nationality", False),
    ("skills_arr", "skill", True),
    ("industries_arr", "industry", True),
)


def load_artifact(cursor, source_code: str, artifact_filename: str):
    cursor.execute(
        """
        SELECT s.source_id, s.permission_status, s.allow_store_metadata,
               s.allow_store_description, a.content_json, a.artifact_date,
               a.file_name, a.artifact_id
        FROM crawl_artifacts AS a
        JOIN job_sources AS s ON s.source_id = a.source_id
        WHERE s.code = %s
          AND a.file_name = %s
        ORDER BY a.created_at DESC
        LIMIT 1
        """,
        (source_code, artifact_filename),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(
            f"No stored crawl artifact found for source={source_code!r}, "
            f"file={artifact_filename!r}."
        )

    payload = row[4]
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("The selected JSONB artifact must contain a top-level jobs array.")
    return {
        "source_id": row[0],
        "permission_status": row[1],
        "allow_store_metadata": row[2],
        "allow_store_description": row[3],
        "payload": payload,
        "artifact_date": row[5],
        "file_name": row[6],
        "artifact_id": row[7],
    }


def company_values(company: dict[str, Any]):
    source_key = company.get("id")
    source_key = str(source_key) if source_key is not None else None
    return {
        "source_company_key": source_key,
        "display_name": text_or_none(company.get("display_name")),
        "logo_url": text_or_none(company.get("image_logo")),
        "cover_image_url": text_or_none(company.get("image_cover")),
        "source_slug": text_or_none(company.get("slug")),
        "source_url": text_or_none(company.get("detail_url")),
        "tagline": text_or_none(company.get("tagline")),
        "company_size_label": text_or_none(company.get("company_size")),
        "num_job_openings": nonnegative_int(company.get("num_job_openings")),
        # Preserve ranges such as "1-10" in the label; only store exact counts.
        "num_employees": nonnegative_int(company.get("num_employees")),
    }


def upsert_company(cursor, source_id, job_source_key: str, company: Any):
    if not isinstance(company, dict):
        return None
    values = company_values(company)
    if not values["display_name"]:
        return None

    if values["source_company_key"] is None:
        # Without a source company key, keep this company record private to the
        # job. Do not merge different companies just because their names match.
        company_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"it-job-platform:{source_id}:{job_source_key}:company",
        )
        cursor.execute(
            """
            INSERT INTO companies (
                company_id, source_id, source_company_key, display_name,
                logo_url, cover_image_url, source_slug, source_url, tagline,
                company_size_label, num_job_openings, num_employees
            ) VALUES (
                %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (company_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                logo_url = EXCLUDED.logo_url,
                cover_image_url = EXCLUDED.cover_image_url,
                source_slug = EXCLUDED.source_slug,
                source_url = EXCLUDED.source_url,
                tagline = EXCLUDED.tagline,
                company_size_label = EXCLUDED.company_size_label,
                num_job_openings = EXCLUDED.num_job_openings,
                num_employees = EXCLUDED.num_employees,
                updated_at = CURRENT_TIMESTAMP
            RETURNING company_id
            """,
            (
                company_id,
                source_id,
                values["display_name"],
                values["logo_url"],
                values["cover_image_url"],
                values["source_slug"],
                values["source_url"],
                values["tagline"],
                values["company_size_label"],
                values["num_job_openings"],
                values["num_employees"],
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO companies (
                source_id, source_company_key, display_name, logo_url,
                cover_image_url, source_slug, source_url, tagline,
                company_size_label, num_job_openings, num_employees
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, source_company_key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                logo_url = EXCLUDED.logo_url,
                cover_image_url = EXCLUDED.cover_image_url,
                source_slug = EXCLUDED.source_slug,
                source_url = EXCLUDED.source_url,
                tagline = EXCLUDED.tagline,
                company_size_label = EXCLUDED.company_size_label,
                num_job_openings = EXCLUDED.num_job_openings,
                num_employees = EXCLUDED.num_employees,
                updated_at = CURRENT_TIMESTAMP
            RETURNING company_id
            """,
            (
                source_id,
                values["source_company_key"],
                values["display_name"],
                values["logo_url"],
                values["cover_image_url"],
                values["source_slug"],
                values["source_url"],
                values["tagline"],
                values["company_size_label"],
                values["num_job_openings"],
                values["num_employees"],
            ),
        )
    company_id = cursor.fetchone()[0]
    company_labels = label_rows(company, COMPANY_LABEL_FIELDS)
    if any(field in company for field, _, _ in COMPANY_LABEL_FIELDS):
        cursor.execute("DELETE FROM company_source_labels WHERE company_id = %s", (company_id,))
        cursor.executemany(
            """
            INSERT INTO company_source_labels
                (company_id, source_field, label_type, label_text, position)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (company_id, source_field, position) DO NOTHING
            """,
            [(company_id, *label) for label in company_labels],
        )
    return company_id


def upsert_job(cursor, source_id, record: dict[str, Any], project_track: str):
    source_key = record.get("id")
    title = text_or_none(record.get("title"))
    source_url = text_or_none(record.get("detail_url")) or text_or_none(record.get("job_url"))
    if source_key is None or not title or not source_url:
        raise ValueError("A job is missing source id, title, or source URL.")
    source_key = str(source_key)

    company_id = upsert_company(cursor, source_id, source_key, record.get("company"))
    raw_status = text_or_none(record.get("status_display"))
    cursor.execute(
        """
        INSERT INTO jobs (
            source_id, source_job_key, company_id, title, project_track,
            source_url, application_url, source_slug, source_status_label,
            work_mode, listing_status, published_at, expires_at, refreshed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, source_job_key) DO UPDATE SET
            company_id = EXCLUDED.company_id,
            title = EXCLUDED.title,
            project_track = EXCLUDED.project_track,
            source_url = EXCLUDED.source_url,
            application_url = EXCLUDED.application_url,
            source_slug = EXCLUDED.source_slug,
            source_status_label = EXCLUDED.source_status_label,
            work_mode = EXCLUDED.work_mode,
            listing_status = EXCLUDED.listing_status,
            published_at = COALESCE(EXCLUDED.published_at, jobs.published_at),
            expires_at = COALESCE(EXCLUDED.expires_at, jobs.expires_at),
            refreshed_at = COALESCE(EXCLUDED.refreshed_at, jobs.refreshed_at),
            last_seen_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        RETURNING job_id
        """,
        (
            source_id,
            source_key,
            company_id,
            title,
            project_track,
            source_url,
            text_or_none(record.get("job_url")),
            text_or_none(record.get("slug")),
            raw_status,
            normalize_work_mode(record.get("work_mode")),
            normalize_listing_status(raw_status),
            parse_timestamp(record.get("published")),
            parse_timestamp(record.get("expires")),
            parse_timestamp(record.get("refreshed")),
        ),
    )
    job_id = cursor.fetchone()[0]

    addresses = record.get("addresses")
    if "addresses" in record:
        cursor.execute("DELETE FROM job_locations WHERE job_id = %s", (job_id,))
        if isinstance(addresses, list):
            for position, address in enumerate(addresses):
                if not isinstance(address, dict):
                    continue
                if not any(address.get(key) for key in ("country_code", "province_city", "district", "ward", "address_line")):
                    continue
                cursor.execute(
                    """
                    INSERT INTO job_locations (
                        job_id, position, country_code, province_city,
                        district, ward, address_line
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        job_id,
                        position,
                        text_or_none(address.get("country_code")),
                        text_or_none(address.get("province_city")),
                        text_or_none(address.get("district")),
                        text_or_none(address.get("ward")),
                        text_or_none(address.get("address_line")),
                    ),
                )

    labels = label_rows(record, JOB_LABEL_FIELDS)
    if any(field in record for field, _, _ in JOB_LABEL_FIELDS):
        cursor.execute("DELETE FROM job_source_labels WHERE job_id = %s", (job_id,))
        cursor.executemany(
            """
            INSERT INTO job_source_labels (job_id, source_field, label_type, label_text, position)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (job_id, source_field, position) DO NOTHING
            """,
            [(job_id, *label) for label in labels],
        )

    upsert_compensation(cursor, job_id, record.get("salary"))
    return job_id


def upsert_compensation(cursor, job_id, salary: Any) -> None:
    if not isinstance(salary, dict):
        return
    minimum = decimal_or_none(salary.get("min"))
    maximum = decimal_or_none(salary.get("max"))
    display_text = text_or_none(salary.get("value"))
    currency = text_or_none(salary.get("currency"))
    currency_code = currency.upper() if currency and re.fullmatch(r"[A-Za-z]{3}", currency) else None
    pay_period = text_or_none(salary.get("unit"))
    negotiable = boolean_or_none(salary.get("is_negotiable"))
    if minimum is None and maximum is None and display_text is None:
        return
    if minimum is not None and maximum is not None and maximum < minimum:
        raise ValueError("Salary maximum is lower than minimum.")
    cursor.execute(
        """
        INSERT INTO job_compensations (
            job_id, min_amount, max_amount, currency_code,
            pay_period, display_text, is_negotiable
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_id) DO UPDATE SET
            min_amount = COALESCE(EXCLUDED.min_amount, job_compensations.min_amount),
            max_amount = COALESCE(EXCLUDED.max_amount, job_compensations.max_amount),
            currency_code = COALESCE(EXCLUDED.currency_code, job_compensations.currency_code),
            pay_period = COALESCE(EXCLUDED.pay_period, job_compensations.pay_period),
            display_text = COALESCE(EXCLUDED.display_text, job_compensations.display_text),
            is_negotiable = COALESCE(EXCLUDED.is_negotiable, job_compensations.is_negotiable),
            updated_at = CURRENT_TIMESTAMP
        """,
        (job_id, minimum, maximum, currency_code, pay_period, display_text, negotiable),
    )


def persist_candidates(cursor, artifact, jobs, project_track: str, findings):
    if artifact["permission_status"] != "approved" or not artifact["allow_store_metadata"]:
        raise PermissionError(
            "Candidate storage blocked: source must be approved and allow_store_metadata=true."
        )
    if not artifact["allow_store_description"] and any(
        compose_description_text(record) for record in jobs if isinstance(record, dict)
    ):
        raise PermissionError(
            "Candidate JSON contains job descriptions but allow_store_description is false. "
            "No candidate rows were written."
        )

    status_counts = {"verified": 0, "needs_review": 0, "rejected": 0}
    for record, finding in zip(jobs, findings):
        if finding["errors"]:
            verification_status = "rejected"
        elif finding["warnings"]:
            verification_status = "needs_review"
        else:
            verification_status = "verified"
        status_counts[verification_status] += 1

        source_job_key = text_or_none(record.get("id")) if isinstance(record, dict) else None
        cursor.execute(
            """INSERT INTO job_ingest_candidates (
                   artifact_id, source_id, record_index, source_job_key,
                   project_track, candidate_json, verification_status,
                   validation_errors, validation_warnings, validator_version,
                   load_status
               ) VALUES (
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending'
               )
               ON CONFLICT (artifact_id, record_index) DO UPDATE SET
                   source_job_key = EXCLUDED.source_job_key,
                   project_track = EXCLUDED.project_track,
                   candidate_json = EXCLUDED.candidate_json,
                   verification_status = EXCLUDED.verification_status,
                   validation_errors = EXCLUDED.validation_errors,
                   validation_warnings = EXCLUDED.validation_warnings,
                   validator_version = EXCLUDED.validator_version,
                   checked_at = CURRENT_TIMESTAMP,
                   load_status = CASE
                       WHEN job_ingest_candidates.load_status = 'loaded' THEN 'loaded'
                       ELSE 'pending'
                   END,
                   job_id = CASE
                       WHEN job_ingest_candidates.load_status = 'loaded' THEN job_ingest_candidates.job_id
                       ELSE NULL
                   END,
                   loaded_at = CASE
                       WHEN job_ingest_candidates.load_status = 'loaded' THEN job_ingest_candidates.loaded_at
                       ELSE NULL
                   END,
                   updated_at = CURRENT_TIMESTAMP""",
            (
                artifact["artifact_id"],
                artifact["source_id"],
                finding["index"],
                source_job_key,
                project_track,
                Json(record),
                verification_status,
                Json(finding["errors"]),
                Json(finding["warnings"]),
                VALIDATOR_VERSION,
            ),
        )
    return status_counts


def upsert_description(cursor, job_id, record: dict[str, Any], fetched_at: datetime | None):
    overview_text = compose_description_text(record)
    if overview_text is None:
        return False
    content_hash = hashlib.sha256(overview_text.encode("utf-8")).digest()
    cursor.execute(
        """
        INSERT INTO job_descriptions (
            job_id, overview_text, responsibilities_text, requirements_text,
            benefits_text, fetch_status, content_hash, fetched_at,
            parser_version, permission_scope
        ) VALUES (%s, %s, NULL, NULL, NULL, 'complete', %s, %s, %s, %s)
        ON CONFLICT (job_id) DO UPDATE SET
            overview_text = EXCLUDED.overview_text,
            responsibilities_text = NULL,
            requirements_text = NULL,
            benefits_text = NULL,
            fetch_status = 'complete',
            content_hash = EXCLUDED.content_hash,
            fetched_at = COALESCE(EXCLUDED.fetched_at, job_descriptions.fetched_at),
            parser_version = EXCLUDED.parser_version,
            permission_scope = EXCLUDED.permission_scope,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            job_id,
            overview_text,
            psycopg2.Binary(content_hash),
            fetched_at,
            PARSER_VERSION,
            "allow_store_description",
        ),
    )
    return True


def connect():
    required = ("JOB_POSTGRES_HOST", "JOB_POSTGRES_DB", "JOB_POSTGRES_USER", "JOB_POSTGRES_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing database environment variables: " + ", ".join(missing))
    return psycopg2.connect(
        host=os.environ["JOB_POSTGRES_HOST"],
        port=int(os.environ.get("JOB_POSTGRES_PORT", "5432")),
        dbname=os.environ["JOB_POSTGRES_DB"],
        user=os.environ["JOB_POSTGRES_USER"],
        password=os.environ["JOB_POSTGRES_PASSWORD"],
        connect_timeout=10,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-code", required=True)
    parser.add_argument("--artifact-filename", required=True)
    parser.add_argument("--project-track", required=True, help="Internal website scope, e.g. data")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and report only; do not write OLTP rows")
    mode.add_argument("--verify", action="store_true", help="Validate and persist per-job JSON candidates to staging")
    mode.add_argument("--apply", action="store_true", help="Write validated jobs to the OLTP tables")
    args = parser.parse_args()
    if not args.project_track.strip():
        parser.error("--project-track cannot be empty")

    connection = connect()
    try:
        with connection.cursor() as cursor:
            artifact = load_artifact(cursor, args.source_code, args.artifact_filename)
            jobs = artifact["payload"]["jobs"]
            errors, warnings = print_validation_report(validate_jobs(jobs))

            source_authorized = (
                artifact["permission_status"] == "approved"
                and artifact["allow_store_metadata"]
            )
            print(
                f"source={args.source_code} artifact={artifact['file_name']} "
                f"jobs={len(jobs)} permission_status={artifact['permission_status']} "
                f"allow_store_metadata={artifact['allow_store_metadata']} "
                f"allow_store_description={artifact['allow_store_description']}"
            )
            if args.dry_run:
                if errors:
                    print("dry_run=true; validation errors found; no rows written")
                    return 1
                print("dry_run=true; report only; no staging or OLTP rows written")
                return 0

            if args.verify:
                status_counts = persist_candidates(
                    cursor,
                    artifact,
                    jobs,
                    args.project_track.strip(),
                    validate_jobs(jobs),
                )
                connection.commit()
                print(
                    f"candidates_staged={len(jobs)} verified={status_counts['verified']} "
                    f"needs_review={status_counts['needs_review']} rejected={status_counts['rejected']} "
                    "load_status=pending; no OLTP job rows written"
                )
                return 0

            if errors:
                raise ValueError(f"Input verification failed with {errors} error(s); no OLTP rows were written.")
            if not source_authorized:
                raise PermissionError(
                    "OLTP load blocked: source must be approved and allow_store_metadata=true. "
                    "The source permission record was not changed."
                )

            fetched_at = parse_timestamp(artifact["payload"].get("captured_at"))
            processed = 0
            descriptions_saved = 0
            cursor.execute(
                """SELECT candidate_id, record_index, project_track, candidate_json,
                          verification_status, load_status, validator_version
                   FROM job_ingest_candidates
                   WHERE artifact_id = %s
                   ORDER BY record_index
                   FOR UPDATE""",
                (artifact["artifact_id"],),
            )
            candidates = cursor.fetchall()
            if len(candidates) != len(jobs):
                raise ValueError(
                    "No complete verification staging set found for this artifact; run --verify first."
                )
            if any(row[2] != args.project_track.strip() for row in candidates):
                raise ValueError("--project-track differs from the staged verification; run --verify again.")
            if any(row[6] != VALIDATOR_VERSION for row in candidates):
                raise ValueError("Staged candidates use an old validator; run --verify again.")

            loadable = [row for row in candidates if row[4] == "verified" and row[5] == "pending"]
            already_loaded = sum(row[5] == "loaded" for row in candidates)
            held_for_review = sum(
                row[4] != "verified" and row[5] == "pending" for row in candidates
            )
            for candidate in loadable:
                candidate_id, _, _, record, _, _, _ = candidate
                if not isinstance(record, dict):
                    raise ValueError(f"Staged candidate {candidate_id} is not a JSON object.")
                job_id = upsert_job(cursor, artifact["source_id"], record, args.project_track.strip())
                processed += 1
                if artifact["allow_store_description"]:
                    descriptions_saved += int(upsert_description(cursor, job_id, record, fetched_at))
                cursor.execute(
                    """UPDATE job_ingest_candidates
                       SET load_status = 'loaded', job_id = %s,
                           loaded_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                       WHERE candidate_id = %s""",
                    (job_id, candidate_id),
                )

        connection.commit()
        print(
            f"loaded_jobs={processed} descriptions_saved={descriptions_saved} "
            f"descriptions_skipped={processed - descriptions_saved if not artifact['allow_store_description'] else 0} "
            f"candidates_already_loaded={already_loaded} "
            f"candidates_held_for_review={held_for_review}"
        )
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"load_crawl_artifacts: {exc}", file=sys.stderr)
        raise SystemExit(1)
