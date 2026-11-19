#!/usr/bin/env python3
"""Export embedded Saramin jobs from a saved HTML page, without network access."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_URL = "https://saramin.vn/viec-lam/tim-kiem?job_categories_ids=8"
FLIGHT_PREFIX = "self.__next_f.push([1,"
TEXT_REFERENCE = re.compile(r"\$([0-9a-f]+)\Z")
JOB_EXPORT_FIELDS = frozenset(
    {
        "id",
        "title",
        "level",
        "is_content_image",
        "owned_id",
        "company",
        "extra_skills",
        "skills_str",
        "skills_arr",
        "experiences_str",
        "contract_types_str",
        "job_levels_str",
        "job_levels_arr",
        "addresses",
        "status_display",
        "detail_url",
        "job_url",
        "slug",
        "salary",
        "features",
        "expires",
        "published",
        "refreshed",
        "responsibilities_text",
        "requirements_text",
        "benefits_text",
        "overview_text",
        "work_mode",
    }
)
COMPANY_EXPORT_FIELDS = frozenset(
    {
        "id",
        "display_name",
        "image_logo",
        "slug",
        "detail_url",
        "tagline",
        "company_size",
        "num_job_openings",
        "num_employees",
        "image_cover",
        "nationalities_str",
        "skills_arr",
        "industries_arr",
    }
)
COMPANY_OPTIONAL_FIELDS = {
    "nationalities_str",
    "skills_arr",
    "industries_arr",
}
DESCRIPTION_SECTIONS = (
    ("responsibilities_text", "responsibilities_original"),
    ("requirements_text", "requirements_original"),
    ("benefits_text", "benefits_original"),
)
HTML_MARKUP = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


class _DescriptionTextParser(HTMLParser):
    """Collect readable text from an HTML fragment while dropping markup."""

    BLOCK_TAGS = {
        "article", "blockquote", "dd", "div", "dl", "dt", "h1", "h2", "h3",
        "h4", "h5", "h6", "li", "ol", "p", "section", "table", "tr", "ul",
    }
    IGNORED_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.IGNORED_TAGS:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag == "br" or tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag not in {"img", "input", "meta", "link", "hr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if self.ignored_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag not in {"br", "img", "input", "meta", "link", "hr"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def html_to_text(fragment: str | None) -> str:
    """Convert an embedded HTML description fragment to readable plain text."""
    if not fragment:
        return ""
    parser = _DescriptionTextParser()
    parser.feed(fragment)
    parser.close()
    text = unescape("".join(parser.parts)).replace("\xa0", " ")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def embedded_value_to_text(value: Any) -> str:
    """Extract HTML/text values from nested description fields such as benefits."""
    if isinstance(value, str):
        return html_to_text(value)
    if isinstance(value, list):
        return "\n".join(
            text for text in (embedded_value_to_text(child) for child in value) if text
        )
    if isinstance(value, dict):
        preferred = ("value", "description", "text", "content")
        parts = [embedded_value_to_text(value[key]) for key in preferred if key in value]
        return "\n".join(text for text in parts if text)
    return ""


def clean_embedded_html(value: Any) -> Any:
    """Remove HTML markup from any remaining embedded string values."""
    if isinstance(value, dict):
        return {key: clean_embedded_html(child) for key, child in value.items()}
    if isinstance(value, list):
        return [clean_embedded_html(child) for child in value]
    if isinstance(value, str) and HTML_MARKUP.search(value):
        return html_to_text(value)
    return value


def add_plain_text_descriptions(job: dict[str, Any]) -> None:
    for target_field, source_field in DESCRIPTION_SECTIONS:
        job[target_field] = embedded_value_to_text(job.pop(source_field, None))
    cleaned = clean_embedded_html(job)
    job.clear()
    job.update(cleaned)


def canonical_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.casefold()).strip()


def field_parts(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, dict):
        code = value.get("id")
        name = value.get("value")
        return (
            str(code).strip() if code not in (None, "") else None,
            str(name).strip() if name not in (None, "") else None,
        )
    if isinstance(value, str) and value.strip():
        return None, value.strip()
    return None, None


def compact_address_entries(addresses: Any) -> list[dict[str, Any]]:
    """Keep one compact address object per job location."""
    if not isinstance(addresses, dict):
        return []

    regions = addresses.get("address_region_array") or []
    if isinstance(regions, str):
        regions = [regions]
    if not isinstance(regions, list):
        region_list = addresses.get("address_region_list")
        regions = [part.strip() for part in region_list.split(",") if part.strip()] if isinstance(region_list, str) else []

    codes = addresses.get("address_region_ids") or []
    if not isinstance(codes, list):
        codes = [codes]

    compacted: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    seen_regions: set[str] = set()

    def add_entry(entry: dict[str, Any], fallback_name: str | None, fallback_code: Any) -> None:
        province_code, province_city = field_parts(entry.get("province"))
        province_code = province_code or (str(fallback_code) if fallback_code not in (None, "") else None)
        province_city = province_city or fallback_name
        if canonical_text(province_city) in {"remote", "remote work", "từ xa"}:
            if province_city:
                seen_regions.add(canonical_text(province_city))
            return

        _, district = field_parts(entry.get("district"))
        _, ward = field_parts(entry.get("ward"))
        address_line = entry.get("street")
        if not isinstance(address_line, str) or not address_line.strip():
            address_line = entry.get("full_address")
            if isinstance(address_line, str):
                for component in (province_city, district, ward):
                    if component:
                        suffix = re.compile(rf"(?:,\s*)?{re.escape(component)}\s*$", re.IGNORECASE)
                        address_line = suffix.sub("", address_line).strip(" ,")
        address_line = address_line.strip() if isinstance(address_line, str) else None
        country_code = entry.get("country_code") or ("VN" if province_code or province_city else None)
        if country_code:
            country_code = str(country_code).upper()

        if not any((country_code, province_city, district, ward, address_line)):
            return

        record = {
            "country_code": country_code,
            "province_city": province_city or None,
            "district": district or None,
            "ward": ward or None,
            "address_line": address_line or None,
        }
        key = tuple(canonical_text(str(record[field] or "")) for field in record)
        if key not in seen:
            compacted.append(record)
            seen.add(key)
        if province_city:
            seen_regions.add(canonical_text(province_city))

    entries = addresses.get("collection_addresses")
    if isinstance(entries, list):
        for index, entry in enumerate(entries):
            if isinstance(entry, dict):
                fallback_name = regions[index] if index < len(regions) and isinstance(regions[index], str) else None
                fallback_code = codes[index] if index < len(codes) else None
                add_entry(entry, fallback_name, fallback_code)

    for index, region in enumerate(regions):
        if not isinstance(region, str) or canonical_text(region) in seen_regions:
            continue
        code = codes[index] if index < len(codes) else None
        add_entry({"province": {"id": code, "value": region}}, region, code)

    return compacted


def infer_work_mode(source_mode: Any, addresses: Any) -> str | None:
    mode = canonical_text(str(source_mode or ""))
    if "từ xa" in mode or "remote" in mode:
        return "remote"
    if "hybrid" in mode or "kết hợp" in mode:
        return "hybrid"
    if "trực tiếp" in mode or "onsite" in mode or "on-site" in mode:
        return "onsite"

    if isinstance(addresses, dict):
        regions = addresses.get("address_region_array") or []
        if isinstance(regions, str):
            regions = [regions]
        if any(canonical_text(str(region)) == "remote" for region in regions):
            return "remote"
    return None


def compact_company_metadata(company: dict[str, Any]) -> dict[str, Any]:
    """Keep the selected company fields and omit empty optional metadata."""
    compacted = {
        key: value
        for key, value in company.items()
        if key in COMPANY_EXPORT_FIELDS
    }
    for key in COMPANY_OPTIONAL_FIELDS:
        value = compacted.get(key)
        if value is None or value == "" or value == []:
            compacted.pop(key, None)
    return compacted


class ExtractionError(RuntimeError):
    pass


def extract_flight_payload(html: str) -> str:
    decoder = json.JSONDecoder()
    chunks: list[str] = []
    position = 0
    while True:
        marker = html.find(FLIGHT_PREFIX, position)
        if marker < 0:
            break
        value_start = marker + len(FLIGHT_PREFIX)
        try:
            value, consumed = decoder.raw_decode(html[value_start:])
        except json.JSONDecodeError:
            position = value_start
            continue
        if isinstance(value, str):
            chunks.append(value)
        position = value_start + consumed
    if not chunks:
        raise ExtractionError("No Next.js Flight payload found in the HTML file.")
    return "".join(chunks)


def extract_jobs_arrays(flight: str) -> list[list[Any]]:
    decoder = json.JSONDecoder()
    arrays: list[list[Any]] = []
    marker_text = '"jobs":'
    position = 0
    while True:
        marker = flight.find(marker_text, position)
        if marker < 0:
            break
        start = flight.find("[", marker + len(marker_text))
        if start < 0:
            break
        try:
            value, consumed = decoder.raw_decode(flight[start:])
        except json.JSONDecodeError:
            position = marker + len(marker_text)
            continue
        if isinstance(value, list):
            arrays.append(value)
        position = start + max(consumed, 1)
    return arrays


def select_detailed_jobs(arrays: list[list[Any]]) -> list[dict[str, Any]]:
    candidates = []
    for array in arrays:
        if not array or not all(isinstance(row, dict) for row in array):
            continue
        keys = set().union(*(row.keys() for row in array))
        if "title" in keys and "responsibilities_original" in keys:
            candidates.append(array)
    if not candidates:
        raise ExtractionError("No detailed job array found in the Flight payload.")
    return max(candidates, key=len)


def walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)


def extract_text_chunks(flight: str, jobs: list[dict[str, Any]]) -> dict[str, str]:
    ref_ids = sorted(
        {
            match.group(1)
            for job in jobs
            for value in walk_strings(job)
            if (match := TEXT_REFERENCE.fullmatch(value))
        }
    )
    utf8 = flight.encode("utf-8")
    chunks: dict[str, str] = {}
    for ref_id in ref_ids:
        header = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ref_id)}:T([0-9a-fA-F]+),")
        matches = list(header.finditer(flight))
        if len(matches) != 1:
            raise ExtractionError(
                f"Expected one text chunk for reference {ref_id}; found {len(matches)}."
            )
        match = matches[0]
        byte_count = int(match.group(1), 16)
        byte_start = len(flight[: match.end()].encode("utf-8"))
        chunk_bytes = utf8[byte_start : byte_start + byte_count]
        if len(chunk_bytes) != byte_count:
            raise ExtractionError(f"Text chunk {ref_id} is truncated.")
        chunks[ref_id] = chunk_bytes.decode("utf-8")
    return chunks


def resolve_and_filter(value: Any, chunks: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: resolve_and_filter(child, chunks)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [resolve_and_filter(child, chunks) for child in value]
    if isinstance(value, str):
        match = TEXT_REFERENCE.fullmatch(value)
        if match and match.group(1) in chunks:
            return chunks[match.group(1)]
    return value


def build_company_map(
    arrays: list[list[Any]], jobs: list[dict[str, Any]]
) -> dict[Any, dict[str, Any]]:
    job_ids = {job.get("id") for job in jobs}
    companies: dict[Any, dict[str, Any]] = {}
    for array in arrays:
        for row in array:
            if (
                isinstance(row, dict)
                and row.get("id") in job_ids
                and isinstance(row.get("company"), dict)
            ):
                companies.setdefault(row["id"], row["company"])
    return companies


def apply_description_supplements(
    jobs: list[dict[str, Any]], supplements_path: Path
) -> None:
    supplement_document = json.loads(supplements_path.read_text(encoding="utf-8"))
    supplements = supplement_document.get("jobs", [])
    if not isinstance(supplements, list):
        raise ExtractionError("Description supplements must contain a jobs array.")

    by_source_id: dict[str, dict[str, str]] = {}
    allowed_fields = {"overview_text"}
    for supplement in supplements:
        if not isinstance(supplement, dict) or supplement.get("source_job_id") is None:
            raise ExtractionError("Each description supplement needs a source_job_id.")
        fields = {
            field: value.strip()
            for field, value in supplement.items()
            if field in allowed_fields and isinstance(value, str) and value.strip()
        }
        by_source_id[str(supplement["source_job_id"])] = fields

    for job in jobs:
        fields = by_source_id.get(str(job.get("id")))
        if fields:
            job.update(fields)


def build_export(
    source: Path, source_url: str, supplements_path: Path | None = None
) -> dict[str, Any]:
    html = source.read_text(encoding="utf-8", errors="replace")
    flight = extract_flight_payload(html)
    arrays = extract_jobs_arrays(flight)
    jobs = select_detailed_jobs(arrays)
    chunks = extract_text_chunks(flight, jobs)
    companies = build_company_map(arrays, jobs)

    exported_jobs = []
    for job in jobs:
        exported = resolve_and_filter(job, chunks)
        if job.get("id") in companies:
            exported["company"] = companies[job["id"]]
        add_plain_text_descriptions(exported)

        source_addresses = exported.get("addresses")
        source_work_mode = exported.pop("job_types_str", None)
        exported["addresses"] = compact_address_entries(source_addresses)
        exported["work_mode"] = infer_work_mode(source_work_mode, source_addresses)
        exported = {
            key: value for key, value in exported.items() if key in JOB_EXPORT_FIELDS
        }
        company = exported.get("company")
        if isinstance(company, dict):
            company = dict(company)
            company.pop("addresses", None)
            exported["company"] = compact_company_metadata(company)

        exported_jobs.append(exported)

    if supplements_path is not None:
        apply_description_supplements(exported_jobs, supplements_path)

    captured_at = datetime.fromtimestamp(source.stat().st_mtime).astimezone()
    document = {
        "source_url": source_url,
        "raw_html_file": source.name,
        "captured_at": captured_at.isoformat(timespec="seconds"),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedded_job_count": len(exported_jobs),
        "resolved_text_reference_count": len(chunks),
        "jobs": exported_jobs,
    }
    if supplements_path is not None:
        document["supplemental_data_file"] = supplements_path.name
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="Saved Saramin HTML file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="JSON output")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument(
        "--supplements", type=Path, help="Optional JSON sidecar with manually sourced text"
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing output")
    args = parser.parse_args()

    source = args.html.resolve()
    output = args.output.resolve()
    if not source.is_file():
        parser.error(f"HTML file does not exist: {source}")
    if source == output:
        parser.error("Input and output paths must be different.")
    supplements = args.supplements.resolve() if args.supplements else None
    if supplements is not None and not supplements.is_file():
        parser.error(f"Description supplements file does not exist: {supplements}")
    if output.exists() and not args.force:
        parser.error(f"Output already exists; pass --force to replace it: {output}")

    try:
        document = build_export(source, args.source_url, supplements)
    except (OSError, json.JSONDecodeError, ExtractionError) as error:
        parser.error(str(error))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Exported {document['embedded_job_count']} jobs; "
        f"resolved {document['resolved_text_reference_count']} text references to {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
