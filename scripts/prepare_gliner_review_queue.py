"""Build a human-review queue for the GLiNER skill fine-tuning pilot.

The current benchmark is a draft, so this script only prepares candidates. It
does not turn them into training labels or treat model proposals as ground truth.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "web/static/data/skill_benchmark_v0.json"
RAW_JOBS_PATH = ROOT / "data/staging/saramin/embedded_jobs_2026-11-09.json"
FILTERED_SKILLS_PATH = ROOT / "data/skill_benchmark_gliner_label_filtered.md"
OUTPUT_CSV_PATH = ROOT / "data/gliner_finetune_review_queue.csv"

# Keep every split at the job level to avoid text from one job appearing in
# both training and evaluation. These IDs cover varied job families and levels.
HOLDOUT_EVAL_JOB_IDS = {"2144686", "2143927", "2139328", "2141955"}
VALIDATION_JOB_IDS = {"2143923", "2138202"}

CSV_FIELDS = [
    "candidate_id",
    "split",
    "job_id",
    "job_title",
    "candidate_kind",
    "candidate_skill",
    "source_section",
    "source_surface",
    "span_start_char",
    "span_end_char_exclusive",
    "model_confidence",
    "proposed_gliner_label",
    "context",
    "human_decision",
    "approved_surface",
    "approved_section",
    "approved_gliner_label",
    "notes",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_filtered_skills() -> set[str]:
    text = FILTERED_SKILLS_PATH.read_text(encoding="utf-8")
    return {
        line[2:].strip().casefold()
        for line in text.splitlines()
        if line.startswith("- ")
    }


def split_sections(value: str | list[str] | None, *, default_both: bool = False) -> list[str]:
    allowed = {"requirements", "responsibilities"}
    if not value:
        return sorted(allowed) if default_both else []
    if isinstance(value, list):
        found = [section for section in value if section in allowed]
        return found or (sorted(allowed) if default_both else [])
    found = [section for section in allowed if re.search(rf"\b{section}\b", value, re.I)]
    return found or (sorted(allowed) if default_both else [])


def as_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def as_label(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value or "")


def find_occurrences(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    """Find exact case-insensitive term spans, avoiding substring word matches."""
    found: dict[tuple[int, int], str] = {}
    for term in terms:
        if not term:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            found.setdefault((match.start(), match.end()), text[match.start():match.end()])
    return [(start, end, surface) for (start, end), surface in sorted(found.items())]


def context_for(text: str, start: int, end: int, window: int = 110) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return " ".join(text[left:right].split())


def split_for(job_id: str) -> str:
    if job_id in HOLDOUT_EVAL_JOB_IDS:
        return "holdout_eval"
    if job_id in VALIDATION_JOB_IDS:
        return "validation"
    return "train"


def main() -> None:
    benchmark = read_json(BENCHMARK_PATH)
    raw = read_json(RAW_JOBS_PATH)
    raw_jobs = {str(job["id"]): job for job in raw["jobs"]}
    filtered = load_filtered_skills()

    available_ids = set(raw_jobs)
    if not HOLDOUT_EVAL_JOB_IDS <= available_ids or not VALIDATION_JOB_IDS <= available_ids:
        raise ValueError("A configured split job ID is missing from the raw job file.")
    if HOLDOUT_EVAL_JOB_IDS & VALIDATION_JOB_IDS:
        raise ValueError("Validation and held-out job splits overlap.")

    output_rows: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    candidate_number = 0

    for benchmark_job in benchmark["rows"]:
        job_id = str(benchmark_job["job_id"])
        if job_id not in raw_jobs:
            raise ValueError(f"Benchmark job {job_id} is missing from raw jobs.")
        source_job = raw_jobs[job_id]
        sections = {
            "requirements": source_job.get("requirements_text") or "",
            "responsibilities": source_job.get("responsibilities_text") or "",
        }

        candidates: list[dict[str, Any]] = []
        for item in benchmark_job.get("found", []):
            if item["skill"].casefold() not in filtered:
                continue
            candidates.append({
                "kind": "gold_found_candidate",
                "skill": item["skill"],
                "terms": as_terms(item.get("model_surface")) + as_terms(item.get("gold_variants")),
                "sections": split_sections(item.get("sections"), default_both=True),
                "confidence": item.get("confidence"),
                "label": as_label(item.get("labels")),
            })

        for item in benchmark_job.get("missed", []):
            if item["skill"].casefold() not in filtered:
                continue
            candidates.append({
                "kind": "gold_missed_candidate",
                "skill": item["skill"],
                "terms": as_terms(item.get("gold_variants")) + [item["skill"]],
                "sections": ["requirements", "responsibilities"],
                "confidence": "",
                "label": "",
            })

        # Keep every unmatched model proposal, including terms outside the 305
        # retained gold vocabulary, because each is a possible false positive.
        for item in benchmark_job.get("extras", []):
            candidates.append({
                "kind": "model_extra_candidate",
                "skill": item["skill"],
                "terms": as_terms(item.get("surface_forms")) + [item["skill"]],
                "sections": split_sections(item.get("sections"), default_both=True),
                "confidence": item.get("confidence", ""),
                "label": as_label(item.get("labels")),
            })

        for candidate in candidates:
            counters[candidate["kind"]] += 1
            occurrences: list[tuple[str, int, int, str]] = []
            for section in candidate["sections"]:
                text = sections.get(section, "")
                for start, end, surface in find_occurrences(text, candidate["terms"]):
                    occurrences.append((section, start, end, surface))

            if not occurrences:
                occurrences = [(candidate["sections"][0] if candidate["sections"] else "", -1, -1, "")]

            for section, start, end, surface in occurrences:
                candidate_number += 1
                text = sections.get(section, "")
                if start >= 0:
                    context = context_for(text, start, end)
                    counters["exact_occurrence_rows"] += 1
                else:
                    context = "Không tìm thấy nguyên văn trong đoạn này; hãy kiểm tra mô tả gốc theo job_id/section."
                    counters["unlocated_candidate_rows"] += 1
                output_rows.append({
                    "candidate_id": f"GLR-{candidate_number:05d}",
                    "split": split_for(job_id),
                    "job_id": job_id,
                    "job_title": source_job.get("title", benchmark_job.get("title", "")),
                    "candidate_kind": candidate["kind"],
                    "candidate_skill": candidate["skill"],
                    "source_section": section,
                    "source_surface": surface,
                    "span_start_char": start if start >= 0 else "",
                    "span_end_char_exclusive": end if end >= 0 else "",
                    "model_confidence": candidate["confidence"],
                    "proposed_gliner_label": candidate["label"],
                    "context": context,
                    "human_decision": "",
                    "approved_surface": "",
                    "approved_section": "",
                    "approved_gliner_label": "",
                    "notes": "",
                })

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} review rows to {OUTPUT_CSV_PATH}")
    print(f"Candidate counts: {dict(counters)}")
    print(f"Jobs by split: {dict(Counter(split_for(str(row['job_id'])) for row in benchmark['rows']))}")


if __name__ == "__main__":
    main()
