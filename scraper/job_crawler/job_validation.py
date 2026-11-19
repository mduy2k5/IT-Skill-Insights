"""Reusable validation and normalization for extracted job records."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DESCRIPTION_SOURCE_FIELDS = (
    "overview_text",
    "responsibilities_text",
    "requirements_text",
    "benefits_text",
)
VALIDATOR_VERSION = "job-input-v1"

try:
    SOURCE_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:
    SOURCE_TIMEZONE = timezone(timedelta(hours=7))


def parse_timestamp(value: Any) -> datetime | None:
    """Parse source timestamps, which may be ISO or `HH:MM:SS DD-MM-YYYY`."""
    if isinstance(value, dict):
        value = value.get("datetime")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(iso_text)
        except ValueError:
            parsed = None
            for date_format in (
                "%H:%M:%S %d-%m-%Y",
                "%d-%m-%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    parsed = datetime.strptime(text, date_format)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SOURCE_TIMEZONE)
    return parsed.astimezone(timezone.utc)


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return str(value)


def nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def boolean_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "negotiable"}:
            return True
        if normalized in {"0", "false", "no", "n", ""}:
            return False
    return None


def normalize_work_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"onsite", "remote", "hybrid"}:
        return normalized
    return "unknown"


def normalize_listing_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"open", "active", "đang tuyển", "đang nhận hồ sơ"}:
        return "active"
    if normalized in {"expired", "closed", "đã hết hạn", "hết hạn"}:
        return "expired"
    if normalized in {"removed", "deleted", "đã gỡ"}:
        return "removed"
    return "unknown"


def compose_description_text(record: dict[str, Any]) -> str | None:
    """Join already-extracted text sections into one overview without parsing HTML."""
    parts = []
    seen = set()
    for field in DESCRIPTION_SOURCE_FIELDS:
        value = text_or_none(record.get(field))
        if value is None:
            continue
        part = value.strip()
        if part and part not in seen:
            parts.append(part)
            seen.add(part)
    return "\n\n".join(parts) or None


def validate_jobs(jobs: list[Any]) -> list[dict[str, Any]]:
    """Check job records before any OLTP write and return per-record findings."""
    ids = [text_or_none(job.get("id")) for job in jobs if isinstance(job, dict)]
    duplicate_ids = {job_id for job_id, count in Counter(ids).items() if job_id and count > 1}
    findings = []

    if not jobs:
        return [{"index": 0, "job_id": "-", "title": "artifact", "errors": ["jobs array is empty"], "warnings": []}]

    for index, record in enumerate(jobs, start=1):
        item = {
            "index": index,
            "job_id": "-",
            "title": "(không có tiêu đề)",
            "errors": [],
            "warnings": [],
        }
        if not isinstance(record, dict):
            item["errors"].append("record is not a JSON object")
            findings.append(item)
            continue

        source_job_key = text_or_none(record.get("id"))
        title = text_or_none(record.get("title"))
        source_url = text_or_none(record.get("detail_url")) or text_or_none(record.get("job_url"))
        item["job_id"] = source_job_key or "-"
        item["title"] = (title or "(không có tiêu đề)")[:90]

        if source_job_key is None:
            item["errors"].append("missing source job id")
        elif source_job_key in duplicate_ids:
            item["errors"].append("duplicate source job id in artifact")
        if title is None:
            item["errors"].append("missing title")
        if source_url is None:
            item["errors"].append("missing source URL")
        elif len(source_url) > 2048:
            item["errors"].append("source URL exceeds 2048 characters")
        else:
            try:
                parsed_url = urlsplit(source_url)
                if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                    item["errors"].append("source URL must be an absolute http(s) URL")
            except ValueError:
                item["errors"].append("source URL is malformed")

        company = record.get("company")
        if not isinstance(company, dict) or not text_or_none(company.get("display_name")):
            item["warnings"].append("company name is missing")

        description = compose_description_text(record)
        if description is None:
            item["warnings"].append("job description is missing")
        elif len(description) < 80:
            item["warnings"].append(f"job description is short ({len(description)} characters)")

        addresses = record.get("addresses")
        has_location = isinstance(addresses, list) and any(
            isinstance(address, dict)
            and any(address.get(field) for field in ("province_city", "district", "ward", "address_line"))
            for address in addresses
        )
        # Remote jobs can legitimately have no physical location. Keep the
        # 0..N OLTP/OLAP location model consistent with verification.
        if not has_location and normalize_work_mode(record.get("work_mode")) != "remote":
            if not isinstance(addresses, list) or not addresses:
                item["warnings"].append("location is missing")
            else:
                item["warnings"].append("addresses contain no usable location fields")

        salary = record.get("salary")
        if not isinstance(salary, dict):
            item["warnings"].append("salary data is missing")
        else:
            minimum_raw = salary.get("min")
            maximum_raw = salary.get("max")
            minimum = decimal_or_none(minimum_raw)
            maximum = decimal_or_none(maximum_raw)
            if minimum_raw is not None and minimum is None:
                item["warnings"].append("minimum salary is not a valid nonnegative number")
            if maximum_raw is not None and maximum is None:
                item["warnings"].append("maximum salary is not a valid nonnegative number")
            if minimum is not None and maximum is not None and maximum < minimum:
                item["errors"].append("maximum salary is lower than minimum salary")

        for field in ("published", "expires", "refreshed"):
            value = record.get(field)
            if value is not None and parse_timestamp(value) is None:
                item["warnings"].append(f"{field} timestamp could not be parsed")

        if normalize_work_mode(record.get("work_mode")) == "unknown":
            item["warnings"].append("work mode is unknown")
        if normalize_listing_status(record.get("status_display")) == "unknown":
            item["warnings"].append("listing status is unknown")

        findings.append(item)
    return findings


def print_validation_report(findings: list[dict[str, Any]]) -> tuple[int, int]:
    """Print a compact validation report and return error and warning totals."""
    errors = sum(len(item["errors"]) for item in findings)
    warnings = sum(len(item["warnings"]) for item in findings)
    for item in findings:
        for message in item["errors"]:
            print(f"ERROR job={item['job_id']} title={item['title']}: {message}")
        for message in item["warnings"]:
            print(f"WARN  job={item['job_id']} title={item['title']}: {message}")
    total = max((item["index"] for item in findings), default=0)
    ready = sum(item["index"] > 0 and not item["errors"] for item in findings)
    print(
        f"verify_summary total={total} ready={ready} "
        f"errors={errors} warnings={warnings}"
    )
    return errors, warnings
