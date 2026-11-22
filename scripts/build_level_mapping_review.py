#!/usr/bin/env python3
"""Build an auditable level-mapping review set from the frozen v0.1 jobs."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = (
    ROOT
    / "data"
    / "archive"
    / "saramin"
    / "snapshot-2026-11-09"
    / "embedded_jobs_text_2026-11-09.json"
)
BENCHMARK_PATH = ROOT / "web" / "static" / "data" / "skill_benchmark_v0_1.json"
OUTPUT_PATH = ROOT / "web" / "static" / "data" / "level_mapping_review_v0_1.json"

HYPOTHESES = {
    "Thực tập": "Intern",
    "Nhân viên": "Fresher",
    "Chuyên viên": "Junior",
    "Chuyên viên cấp cao": "Senior",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    snapshot = read_json(SNAPSHOT_PATH)
    benchmark = read_json(BENCHMARK_PATH)
    source_jobs = {str(job["id"]): job for job in snapshot["jobs"]}

    jobs = []
    membership_count = 0
    for benchmark_row in benchmark["rows"]:
        job_id = str(benchmark_row["job_id"])
        source = source_jobs.get(job_id)
        if source is None:
            raise SystemExit(f"Job {job_id} is missing from the archived Saramin snapshot.")

        labels = source.get("job_levels_arr") or []
        ids = source.get("job_levels_ids") or []
        hypotheses = []
        for index, label in enumerate(labels):
            candidate = HYPOTHESES.get(label)
            if candidate is None:
                raise SystemExit(f"No review hypothesis is defined for source label {label!r}.")
            hypotheses.append(
                {
                    "source_label": label,
                    "source_label_id": ids[index] if index < len(ids) else None,
                    "candidate_level": candidate,
                }
            )

        membership_count += len(hypotheses)
        jobs.append(
            {
                "job_id": job_id,
                "title": benchmark_row["title"],
                "hypotheses": hypotheses,
                "experience_label": benchmark_row.get("experience_label") or "",
                "requirements_text": source.get("requirements_text") or "",
                "responsibilities_text": source.get("responsibilities_text") or "",
            }
        )

    payload = {
        "version": "0.1",
        "status": "pending_human_review",
        "source_snapshot": "data/archive/saramin/snapshot-2026-11-09/embedded_jobs_text_2026-11-09.json",
        "review_unit": "one source-level label membership in one job",
        "job_count": len(jobs),
        "membership_count": membership_count,
        "mapping_hypotheses": [
            {"source_label": label, "candidate_level": candidate}
            for label, candidate in HYPOTHESES.items()
        ],
        "review_status_options": ["consistent", "contradictory", "unclear"],
        "jobs": jobs,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {membership_count} review units across {len(jobs)} jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
