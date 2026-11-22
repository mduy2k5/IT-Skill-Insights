"""Load verified, permission-approved OLTP jobs into the DuckDB warehouse.

Run through the one-shot Compose service with --dry-run or --apply. The
PostgreSQL role only reads olap_verified_jobs and the public OLTP tables; the
candidate JSON and full job descriptions are never copied into DuckDB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo
from uuid import UUID

import duckdb
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid

register_uuid()
REPORTING_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
ALLOWED_WORK_MODES = {"onsite", "remote", "hybrid", "unknown"}
ALLOWED_LISTING_STATUSES = {"active", "expired", "removed", "unknown"}
RAW_SKILL_TAXONOMY_VERSION = "source-label-v1"
RAW_SENIORITY_MAPPING_VERSION = "source-label-v1"


def postgres_connection():
    required = (
        "JOB_POSTGRES_HOST",
        "JOB_POSTGRES_DB",
        "JOB_POSTGRES_USER",
        "JOB_POSTGRES_PASSWORD",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing PostgreSQL settings: " + ", ".join(missing))

    connection = psycopg2.connect(
        host=os.environ["JOB_POSTGRES_HOST"],
        port=int(os.environ.get("JOB_POSTGRES_PORT", "5432")),
        dbname=os.environ["JOB_POSTGRES_DB"],
        user=os.environ["JOB_POSTGRES_USER"],
        password=os.environ["JOB_POSTGRES_PASSWORD"],
        connect_timeout=10,
        application_name="it_job_olap_loader",
    )
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
    return connection


def authorized_source(pg, source_code: str) -> dict[str, Any]:
    with pg.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """SELECT source_id, code, display_name, base_url,
                      permission_status, allow_store_metadata
               FROM job_sources WHERE code = %s""",
            (source_code,),
        )
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Unknown source code: {source_code}")
    if row["permission_status"] != "approved" or not row["allow_store_metadata"]:
        raise PermissionError(
            "OLAP load blocked: source must be approved and allow_store_metadata=true."
        )
    return dict(row)


def iter_verified_jobs(pg, source_code: str, project_track: str, batch_size: int):
    query = """SELECT job_id, source_id, source_code, source_display_name,
                      source_base_url, allow_analyze_description,
                      source_job_key, company_id, title, project_track,
                      source_url, work_mode, listing_status, published_at,
                      expires_at, first_seen_at, last_seen_at
               FROM olap_verified_jobs
               WHERE source_code = %s AND project_track = %s
               ORDER BY job_id"""
    with pg.cursor(name="olap_verified_job_export", cursor_factory=RealDictCursor) as cursor:
        cursor.itersize = batch_size
        cursor.execute(query, (source_code, project_track))
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield [dict(row) for row in rows]


def fetch_related(pg, job_ids: list[uuid.UUID], company_ids: list[uuid.UUID]):
    jobs: dict[str, dict[str, Any]] = {}
    locations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, list[dict[str, Any]]] = defaultdict(list)
    compensations: dict[str, dict[str, Any]] = {}
    companies: dict[str, dict[str, Any]] = {}

    with pg.cursor(cursor_factory=RealDictCursor) as cursor:
        if company_ids:
            cursor.execute(
                """SELECT company_id, source_id, source_company_key,
                          display_name, company_size_label
                   FROM companies WHERE company_id = ANY(%s)""",
                (company_ids,),
            )
            companies = {str(row["company_id"]): dict(row) for row in cursor.fetchall()}

        cursor.execute(
            """SELECT job_id, min_amount, max_amount, currency_code, pay_period
               FROM job_compensations WHERE job_id = ANY(%s)""",
            (job_ids,),
        )
        compensations = {str(row["job_id"]): dict(row) for row in cursor.fetchall()}

        cursor.execute(
            """SELECT job_id, position, country_code, province_city,
                      district, ward, address_line
               FROM job_locations WHERE job_id = ANY(%s)
               ORDER BY job_id, position""",
            (job_ids,),
        )
        for row in cursor.fetchall():
            item = dict(row)
            locations[str(item["job_id"])].append(item)

        cursor.execute(
            """SELECT job_id, source_field, label_type, label_text, position
               FROM job_source_labels WHERE job_id = ANY(%s)
               ORDER BY job_id, source_field, position""",
            (job_ids,),
        )
        for row in cursor.fetchall():
            item = dict(row)
            labels[str(item["job_id"])].append(item)

    return jobs, companies, compensations, locations, labels


def utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def local_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(REPORTING_ZONE).date()
        return value.replace(tzinfo=timezone.utc).astimezone(REPORTING_ZONE).date()
    return value


def date_key(value: date | None) -> int | None:
    return value.year * 10000 + value.month * 100 + value.day if value else None


def date_dimension_values(value: date):
    return (
        date_key(value),
        value,
        value.year,
        (value.month - 1) // 3 + 1,
        value.month,
        date(value.year, value.month, 1),
        value.isocalendar().week,
        value.day,
        value.isoweekday(),
    )


def duckdb_literal(value: Any) -> str:
    """Render a typed SQL literal for Quack (remote prepared binds are unsupported)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, UUID):
        return f"CAST('{value}' AS UUID)"
    if isinstance(value, datetime):
        naive = utc_naive(value)
        return f"TIMESTAMP '{naive.isoformat(sep=' ', timespec='microseconds')}'"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def execute_remote(olap, query: str, values: tuple[Any, ...] = ()):
    """Execute SQL on the Quack server using escaped literals, not bind markers."""
    if not values:
        return olap.execute(query)
    parts = query.split("?")
    if len(parts) != len(values) + 1:
        raise ValueError("OLAP SQL placeholder count does not match its values.")
    rendered = parts[0]
    for index, value in enumerate(values):
        rendered += duckdb_literal(value) + parts[index + 1]
    return olap.execute(rendered)


def stable_location_hash(location: dict[str, Any]) -> str:
    # Hash the exact OLTP fields; no address cleanup/canonicalization is done.
    payload = [
        location.get("country_code"),
        location.get("province_city"),
        location.get("district"),
        location.get("ward"),
        location.get("address_line"),
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def attach_warehouse():
    required = ("JOB_OLAP_TOKEN",)
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing OLAP settings: " + ", ".join(missing))

    host = os.environ.get("JOB_OLAP_HOST", "job-olap")
    port = int(os.environ.get("JOB_OLAP_PORT", "9494"))
    token = os.environ["JOB_OLAP_TOKEN"].replace("'", "''")
    connection = duckdb.connect()
    connection.execute(
        f"ATTACH 'quack:{host}:{port}' AS warehouse_remote "
        f"(TOKEN '{token}', DISABLE_SSL true)"
    )
    connection.execute("CONNECT warehouse_remote")
    return connection


def upsert_source(olap, source: dict[str, Any]) -> int:
    source_id = source["source_id"]
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_source
               (source_id, source_code, display_name, base_url)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (source_id) DO NOTHING""",
        (source_id, source["code"], source["display_name"], source["base_url"]),
    )
    execute_remote(
        olap,
        """UPDATE warehouse.dim_source
           SET source_code = ?, display_name = ?, base_url = ?
           WHERE source_id = ?
             AND (source_code IS DISTINCT FROM ?
               OR display_name IS DISTINCT FROM ?
               OR base_url IS DISTINCT FROM ?)""",
        (
            source["code"], source["display_name"], source["base_url"], source_id,
            source["code"], source["display_name"], source["base_url"],
        ),
    )
    return int(execute_remote(
        olap, "SELECT source_key FROM warehouse.dim_source WHERE source_id = ?", (source_id,)
    ).fetchone()[0])


def upsert_company(olap, source_key: int, company: dict[str, Any]) -> int:
    source_company_key = company["source_company_key"]
    if source_company_key is None:
        # Some OLTP companies are intentionally private to one job and lack a
        # source key. Use the stable OLTP UUID as a warehouse-only fallback.
        source_company_key = f"__oltp_company_id__:{company['company_id']}"
    name = company["display_name"]
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_company
               (source_key, source_company_key, company_name, company_size_label)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (source_key, source_company_key) DO NOTHING""",
        (source_key, source_company_key, name, company["company_size_label"]),
    )
    execute_remote(
        olap,
        """UPDATE warehouse.dim_company
           SET company_name = ?, company_size_label = ?
           WHERE source_key = ? AND source_company_key = ?
             AND (company_name IS DISTINCT FROM ?
               OR company_size_label IS DISTINCT FROM ?)""",
        (
            name, company["company_size_label"], source_key, source_company_key,
            name, company["company_size_label"],
        ),
    )
    return int(execute_remote(
        olap,
        """SELECT company_key FROM warehouse.dim_company
           WHERE source_key = ? AND source_company_key = ?""",
        (source_key, source_company_key),
    ).fetchone()[0])


def upsert_job(olap, source_key: int, job: dict[str, Any]) -> int:
    mode = job["work_mode"] if job["work_mode"] in ALLOWED_WORK_MODES else "unknown"
    status = job["listing_status"] if job["listing_status"] in ALLOWED_LISTING_STATUSES else "unknown"
    values = (
        source_key,
        str(job["source_job_key"]),
        job["title"],
        job["project_track"],
        job["source_url"],
        mode,
        status,
        None,  # Description text stays in OLTP; this loader does not copy it to OLAP.
        utc_naive(job["first_seen_at"]),
        utc_naive(job["last_seen_at"]),
    )
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_job
               (source_key, source_job_key, title, project_track, source_url,
                work_mode, listing_status, description_hash, first_seen_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (source_key, source_job_key) DO NOTHING""",
        values,
    )
    execute_remote(
        olap,
        """UPDATE warehouse.dim_job
           SET title = ?, project_track = ?, source_url = ?, work_mode = ?,
               listing_status = ?, first_seen_at = ?, last_seen_at = ?, is_current = TRUE
           WHERE source_key = ? AND source_job_key = ?
             AND (title IS DISTINCT FROM ?
               OR project_track IS DISTINCT FROM ?
               OR source_url IS DISTINCT FROM ?
               OR work_mode IS DISTINCT FROM ?
               OR listing_status IS DISTINCT FROM ?
               OR first_seen_at IS DISTINCT FROM ?
               OR last_seen_at IS DISTINCT FROM ?
               OR is_current IS DISTINCT FROM TRUE)""",
        (
            job["title"], job["project_track"], job["source_url"], mode, status,
            utc_naive(job["first_seen_at"]), utc_naive(job["last_seen_at"]),
            source_key, str(job["source_job_key"]),
            job["title"], job["project_track"], job["source_url"], mode, status,
            utc_naive(job["first_seen_at"]), utc_naive(job["last_seen_at"]),
        ),
    )
    return int(execute_remote(
        olap,
        """SELECT job_key FROM warehouse.dim_job
           WHERE source_key = ? AND source_job_key = ?""",
        (source_key, str(job["source_job_key"])),
    ).fetchone()[0])


def ensure_dates(olap, values: set[date]) -> dict[date, int]:
    result = {}
    for value in sorted(values):
        execute_remote(
            olap,
            """INSERT INTO warehouse.dim_date
                   (date_key, full_date, calendar_year, calendar_quarter,
                    calendar_month, month_start, iso_week, day_of_month, day_of_week)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (date_key) DO NOTHING""",
            date_dimension_values(value),
        )
        result[value] = int(execute_remote(
            olap, "SELECT date_key FROM warehouse.dim_date WHERE full_date = ?", (value,)
        ).fetchone()[0])
    return result


def upsert_location(olap, location: dict[str, Any]) -> int:
    location_hash = stable_location_hash(location)
    values = (
        location_hash,
        location["country_code"],
        location["province_city"],
        location["district"],
        location["ward"],
        location["address_line"],
    )
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_location
               (location_hash, country_code, province_city, district, ward, address_line)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (location_hash) DO NOTHING""",
        values,
    )
    return int(execute_remote(
        olap, "SELECT location_key FROM warehouse.dim_location WHERE location_hash = ?",
        (location_hash,),
    ).fetchone()[0])


def normalize_raw_skill_name(value: Any) -> str | None:
    if value is None:
        return None
    name = " ".join(str(value).split())
    return name or None


def upsert_skill(olap, raw_name: str) -> None:
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_skill
               (canonical_name, taxonomy_version, is_active)
           VALUES (?, ?, TRUE)
           ON CONFLICT (canonical_name, taxonomy_version)
           DO UPDATE SET is_active = TRUE""",
        (raw_name, RAW_SKILL_TAXONOMY_VERSION),
    )


def upsert_seniority(olap, source_key: int, source_label: str) -> int:
    """Store an identity mapping until a reviewed cross-source taxonomy exists."""
    execute_remote(
        olap,
        """INSERT INTO warehouse.dim_seniority
               (source_key, source_label, normalized_level, mapping_version, is_unknown)
           VALUES (?, ?, ?, ?, FALSE)
           ON CONFLICT (source_key, source_label, mapping_version)
           DO UPDATE SET normalized_level = EXCLUDED.normalized_level,
                         is_unknown = FALSE""",
        (source_key, source_label, source_label, RAW_SENIORITY_MAPPING_VERSION),
    )
    return int(execute_remote(
        olap,
        """SELECT seniority_key FROM warehouse.dim_seniority
           WHERE source_key = ? AND source_label = ? AND mapping_version = ?""",
        (source_key, source_label, RAW_SENIORITY_MAPPING_VERSION),
    ).fetchone()[0])


def load_batch(olap, source_key: int, jobs: list[dict[str, Any]], pg):
    job_ids = [uuid.UUID(str(job["job_id"])) for job in jobs]
    company_ids = sorted({uuid.UUID(str(job["company_id"])) for job in jobs if job["company_id"]})
    _, companies, compensations, locations, labels = fetch_related(pg, job_ids, company_ids)
    skill_names = {
        name
        for job_labels in labels.values()
        for label in job_labels
        if label["label_type"] == "skill"
        if (name := normalize_raw_skill_name(label["label_text"])) is not None
    }
    for skill_name in sorted(skill_names):
        upsert_skill(olap, skill_name)

    seniority_labels_seen = {
        label["label_text"]
        for job_labels in labels.values()
        for label in job_labels
        if label["source_field"] == "job_levels_arr"
        and label["label_type"] == "seniority"
        and label["label_text"]
    }
    seniority_keys = {
        label: upsert_seniority(olap, source_key, label)
        for label in sorted(seniority_labels_seen)
    }

    company_keys = {}
    for company_id, company in companies.items():
        if company["display_name"]:
            company_keys[company_id] = upsert_company(olap, source_key, company)

    published_dates = {local_date(job["published_at"]) for job in jobs if job["published_at"]}
    expiry_dates = {local_date(job["expires_at"]) for job in jobs if job["expires_at"]}
    date_keys = ensure_dates(olap, published_dates | expiry_dates)

    coverage = defaultdict(lambda: {
        "total": 0,
        "with_location": 0,
        "without_location": 0,
        "remote_without_location": 0,
        "latest_date": None,
    })
    counts = {"jobs": 0, "companies": len(company_keys), "locations": 0, "labels": 0}

    for job in jobs:
        job_id = str(job["job_id"])
        job_key = upsert_job(olap, source_key, job)
        counts["jobs"] += 1

        compensation = compensations.get(job_id, {})
        published = local_date(job["published_at"])
        expires = local_date(job["expires_at"])
        company_key = company_keys.get(str(job["company_id"])) if job["company_id"] else None
        mode = job["work_mode"] if job["work_mode"] in ALLOWED_WORK_MODES else "unknown"
        job_seniority_labels = {
            label["label_text"]
            for label in labels.get(job_id, [])
            if label["source_field"] == "job_levels_arr"
            and label["label_type"] == "seniority"
            and label["label_text"]
        }
        seniority_key = (
            seniority_keys[next(iter(job_seniority_labels))]
            if len(job_seniority_labels) == 1
            else None
        )
        execute_remote(
            olap,
            """INSERT INTO warehouse.fact_job_posting
                   (job_key, source_key, published_date_key, expires_date_key,
                    company_key, seniority_key, work_mode, salary_min, salary_max,
                    salary_currency, salary_period, job_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT (job_key) DO UPDATE SET
                   source_key = EXCLUDED.source_key,
                   published_date_key = EXCLUDED.published_date_key,
                   expires_date_key = EXCLUDED.expires_date_key,
                   company_key = EXCLUDED.company_key,
                   seniority_key = EXCLUDED.seniority_key,
                   work_mode = EXCLUDED.work_mode,
                   salary_min = EXCLUDED.salary_min,
                   salary_max = EXCLUDED.salary_max,
                   salary_currency = EXCLUDED.salary_currency,
                   salary_period = EXCLUDED.salary_period""",
            (
                job_key, source_key,
                date_keys.get(published), date_keys.get(expires), company_key, seniority_key,
                mode, compensation.get("min_amount"), compensation.get("max_amount"),
                compensation.get("currency_code"), compensation.get("pay_period"),
            ),
        )

        execute_remote(olap, "DELETE FROM warehouse.bridge_job_location WHERE job_key = ?", (job_key,))
        job_locations = locations.get(job_id, [])
        for location in job_locations:
            location_key = upsert_location(olap, location)
            execute_remote(
                olap,
                """INSERT INTO warehouse.bridge_job_location (job_key, location_key, position)
                   VALUES (?, ?, ?)""",
                (job_key, location_key, location["position"]),
            )
            counts["locations"] += 1

        execute_remote(olap, "DELETE FROM warehouse.bridge_job_source_label WHERE job_key = ?", (job_key,))
        for label in labels.get(job_id, []):
            execute_remote(
                olap,
                """INSERT INTO warehouse.bridge_job_source_label
                       (job_key, source_field, label_type, label_text, position)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    job_key, label["source_field"], label["label_type"],
                    label["label_text"], label["position"],
                ),
            )
            counts["labels"] += 1

        if published:
            month_key = published.year * 10000 + published.month * 100 + 1
            item = coverage[month_key]
            item["total"] += 1
            if job_locations:
                item["with_location"] += 1
            else:
                item["without_location"] += 1
                if mode == "remote":
                    item["remote_without_location"] += 1
            if item["latest_date"] is None or published > item["latest_date"]:
                item["latest_date"] = published

    return counts, coverage, skill_names, seniority_labels_seen


def load_olap(args) -> dict[str, Any]:
    pg = postgres_connection()
    olap = None
    try:
        source = authorized_source(pg, args.source_code)
        batches = iter_verified_jobs(pg, args.source_code, args.project_track, args.batch_size)

        if args.dry_run:
            total = 0
            locationless = 0
            for batch in batches:
                ids = [uuid.UUID(str(row["job_id"])) for row in batch]
                _, _, _, locations, _ = fetch_related(pg, ids, [])
                total += len(batch)
                locationless += sum(str(row["job_id"]) not in locations for row in batch)
            pg.rollback()
            return {
                "status": "dry_run",
                "source": source["code"],
                "project_track": args.project_track,
                "verified_jobs": total,
                "jobs_without_location": locationless,
                "written": False,
            }

        olap = attach_warehouse()
        olap.execute("BEGIN TRANSACTION")
        source_key = upsert_source(olap, source)
        aggregate = {"jobs": 0, "companies": 0, "locations": 0, "labels": 0}
        skill_names_seen: set[str] = set()
        seniority_labels_seen: set[str] = set()
        monthly_coverage: dict[int, dict[str, Any]] = {}
        for batch in batches:
            counts, coverage, skill_names, seniority_labels = load_batch(olap, source_key, batch, pg)
            skill_names_seen.update(skill_names)
            seniority_labels_seen.update(seniority_labels)
            for key, value in counts.items():
                aggregate[key] += value
            for month_key, value in coverage.items():
                current = monthly_coverage.setdefault(month_key, {
                    "total": 0,
                    "with_location": 0,
                    "without_location": 0,
                    "remote_without_location": 0,
                    "latest_date": None,
                })
                for field in ("total", "with_location", "without_location", "remote_without_location"):
                    current[field] += value[field]
                if value["latest_date"] and (
                    current["latest_date"] is None or value["latest_date"] > current["latest_date"]
                ):
                    current["latest_date"] = value["latest_date"]

        execute_remote(
            olap,
            """DELETE FROM warehouse.mart_source_coverage_monthly
               WHERE source_key = ? AND project_track = ?""",
            (source_key, args.project_track),
        )
        for month_key, value in sorted(monthly_coverage.items()):
            execute_remote(
                olap,
                """INSERT INTO warehouse.mart_source_coverage_monthly
                       (month_key, source_key, project_track, total_job_count,
                        jobs_with_location, jobs_without_location,
                        remote_without_location, latest_published_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    month_key, source_key, args.project_track, value["total"],
                    value["with_location"], value["without_location"],
                    value["remote_without_location"], value["latest_date"],
                ),
            )

        olap.execute("COMMIT")
        pg.rollback()
        aggregate["distinct_skill_names_upserted"] = len(skill_names_seen)
        aggregate["distinct_seniority_labels_upserted"] = len(seniority_labels_seen)
        aggregate["months_in_source_coverage_mart"] = len(monthly_coverage)
        aggregate["source_key"] = source_key
        aggregate["status"] = "loaded"
        aggregate["source"] = source["code"]
        aggregate["project_track"] = args.project_track
        return aggregate
    except Exception:
        if olap is not None:
            try:
                olap.execute("ROLLBACK")
            except Exception:
                pass
        pg.rollback()
        raise
    finally:
        if olap is not None:
            olap.close()
        pg.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-code", required=True)
    parser.add_argument("--project-track", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    result = load_olap(args)
    print("OLAP_ETL " + json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"load_olap: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
