import json
import sys

import pandas as pd
import psycopg2

from scraper.job_crawler.transform.weba_transformer import WebATransformer
from scraper.job_crawler.transform import database
from scraper.job_crawler import job_skill_requirement_transform, job_title_transform


SOURCE_LABEL = "WebA"
REQUIRED_SCHEMA_MIGRATION = "001_transform_schema"


def verify_transform_schema(conn):
    """Check migration state without creating or changing database objects."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s",
                (REQUIRED_SCHEMA_MIGRATION,),
            )
            applied = cur.fetchone()
    except psycopg2.Error as exc:
        if getattr(exc, "pgcode", None) == "42P01":
            raise RuntimeError(
                "Clean schema migration 001_transform_schema is missing. "
                "Apply scraper/job_crawler/migrations/001_transform_schema.sql before running transform."
            ) from None
        raise

    if not applied:
        raise RuntimeError(
            "Clean schema migration 001_transform_schema is missing. "
            "Apply scraper/job_crawler/migrations/001_transform_schema.sql before running transform."
        )


def sanitize_error(error):
    message = str(error)
    sensitive_labels = ("password", "passwd", "pwd", "token", "secret", "api_key", "access_key")

    for label in sensitive_labels:
        search_from = 0
        while True:
            lowered = message.lower()
            label_start = lowered.find(label, search_from)
            if label_start < 0:
                break
            value_start = label_start + len(label)
            while value_start < len(message) and message[value_start].isspace():
                value_start += 1
            if value_start >= len(message) or message[value_start] not in ("=", ":"):
                search_from = label_start + len(label)
                continue
            value_start += 1
            while value_start < len(message) and message[value_start].isspace():
                value_start += 1
            quote = message[value_start] if value_start < len(message) and message[value_start] in ("'", '"') else None
            if quote:
                value_start += 1
                value_end = message.find(quote, value_start)
                if value_end < 0:
                    value_end = len(message)
            else:
                value_end = value_start
                while value_end < len(message) and not message[value_end].isspace() and message[value_end] not in (",", ";", ")"):
                    value_end += 1
            message = message[:value_start] + "[REDACTED]" + message[value_end:]
            search_from = value_start + len("[REDACTED]")

    lowered = message.lower()
    for scheme in ("postgres://", "postgresql://"):
        scheme_start = lowered.find(scheme)
        if scheme_start >= 0:
            at_sign = lowered.find("@", scheme_start + len(scheme))
            colon = lowered.find(":", scheme_start + len(scheme))
            if colon >= 0 and at_sign > colon:
                message = message[:colon + 1] + "[REDACTED]" + message[at_sign:]
                lowered = message.lower()

    bearer = lowered.find("bearer ")
    if bearer >= 0:
        value_start = bearer + len("bearer ")
        value_end = value_start
        while value_end < len(message) and not message[value_end].isspace():
            value_end += 1
        message = message[:value_start] + "[REDACTED]" + message[value_end:]

    return message[:500]


def initial_summary():
    return {
        "source": SOURCE_LABEL,
        "status": "running",
        "stages_completed": [],
        "input_jobs": 0,
        "normalized_jobs": 0,
        "inserted_jobs": 0,
        "updated_jobs": 0,
        "unchanged_jobs": 0,
        "mapping_added": 0,
        "mapping_removed": 0,
    }


def complete_stage(summary, stage):
    summary["stages_completed"].append(stage)


def start_stage(summary, stage):
    summary["current_stage"] = stage


def log_summary(summary):
    print("ETL_SUMMARY " + json.dumps(summary, ensure_ascii=False, default=str), flush=True)


def run_job_transform(conn, df, summary, complete):
    stage = "dictionary_load"
    start_stage(summary, stage)
    job_skill_requirement_transform.load_dictionary(conn)
    job_title_transform.load_dictionary(conn)
    complete(summary, stage)

    stage = "normalize"
    start_stage(summary, stage)
    clean_df = WebATransformer(df.copy()).run()
    clean_df["source"] = SOURCE_LABEL
    summary["normalized_jobs"] = len(clean_df)
    complete(summary, stage)

    stage = "dimension_load"
    start_stage(summary, stage)
    database.insert_company_mapping(conn, clean_df)
    database.insert_location_mapping(conn, clean_df)
    database.insert_level_mapping(conn, clean_df)
    database.insert_tag_mapping(conn, clean_df)
    database.insert_date_mapping(conn, clean_df)
    database.insert_job_type_mapping(conn, clean_df)
    complete(summary, stage)

    stage = "clean_upsert"
    start_stage(summary, stage)
    job_stats = database.insert_jobs_clean(conn, clean_df)
    summary["inserted_jobs"] = job_stats["inserted"]
    summary["updated_jobs"] = job_stats["updated"]
    summary["unchanged_jobs"] = job_stats["unchanged"]
    changed_ids = job_stats["changed_ids"]
    complete(summary, stage)

    stage = "title_mapping"
    start_stage(summary, stage)
    title_stats = job_title_transform.reconcile_mappings(conn, changed_ids)
    summary["mapping_added"] += title_stats["added"]
    summary["mapping_removed"] += title_stats["removed"]
    complete(summary, stage)

    stage = "skill_mapping"
    start_stage(summary, stage)
    skill_stats = job_skill_requirement_transform.reconcile_mappings(conn, changed_ids)
    summary["mapping_added"] += skill_stats["added"]
    summary["mapping_removed"] += skill_stats["removed"]
    complete(summary, stage)

    stage = "level_mapping"
    start_stage(summary, stage)
    level_stats = database.sync_job_level_mapping(conn, clean_df, changed_ids)
    summary["mapping_added"] += level_stats["added"]
    summary["mapping_removed"] += level_stats["removed"]
    complete(summary, stage)

    return stage


def main():
    summary = initial_summary()
    conn = None
    stage = "connect"

    try:
        start_stage(summary, stage)
        conn = psycopg2.connect(
            host="postgres",
            database="airflow",
            user="airflow",
            password="airflow",
        )

        stage = "schema_check"
        start_stage(summary, stage)
        verify_transform_schema(conn)
        conn.commit()
        complete_stage(summary, stage)

        stage = "raw_read"
        start_stage(summary, stage)
        raw_df = pd.read_sql_query("SELECT * FROM jobs;", conn)
        conn.commit()
        complete_stage(summary, stage)

        stage = "source_filter"
        start_stage(summary, stage)
        if "source" not in raw_df.columns:
            raise ValueError("The jobs table does not contain a source column.")
        source_df = raw_df[raw_df["source"] == SOURCE_LABEL].copy()
        summary["input_jobs"] = len(source_df)
        complete_stage(summary, stage)

        if source_df.empty:
            summary["status"] = "no_data"
            log_summary(summary)
            return 99

        run_job_transform(conn, source_df, summary, complete_stage)
        stage = "commit"
        start_stage(summary, stage)
        conn.commit()
        complete_stage(summary, "commit")
        summary["status"] = "succeeded"
        log_summary(summary)
        return 0
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        safe_error = sanitize_error(exc)
        summary["status"] = "failed"
        failed_stage = summary.get("current_stage", stage)
        summary["failed_stage"] = failed_stage
        summary["error"] = safe_error
        log_summary(summary)
        raise RuntimeError("Transform failed at " + failed_stage + ": " + safe_error) from None
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
