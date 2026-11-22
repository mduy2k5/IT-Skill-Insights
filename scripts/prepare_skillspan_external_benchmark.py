"""Build a job-level external validation/holdout from SkillSpan TECH.

The script keeps the upstream dev/test boundary, selects only the English TECH
source, reconstructs each posting from its annotated sentences, and preserves
both Skill and Knowledge spans. It never uses the SkillSpan training split.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / ".tmp/skillspan_source"
OUTPUT_DIR = ROOT / "data/skillspan_external"
SPLITS = (("dev", "validation"), ("test", "holdout"))


def sha256(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_bio(tokens: list[str], tags: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert SkillSpan's B/I/O labels to exact character and token spans."""
    if len(tokens) != len(tags):
        raise ValueError("Token/tag count mismatch")

    text = " ".join(tokens)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = cursor
        end = start + len(token)
        offsets.append((start, end))
        cursor = end + 1

    spans: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    active_start: int | None = None
    active_needs_review = False

    def close(end_token: int) -> None:
        nonlocal active_start, active_needs_review
        if active_start is None:
            return
        start_char = offsets[active_start][0]
        end_char = offsets[end_token - 1][1]
        spans.append({
            "start": start_char,
            "end_exclusive": end_char,
            "text": text[start_char:end_char],
            "token_start": active_start,
            "token_end_exclusive": end_token,
            "needs_review": active_needs_review,
        })
        active_start = None
        active_needs_review = False

    for index, tag in enumerate(tags):
        if tag == "B":
            close(index)
            active_start = index
        elif tag == "I":
            if active_start is None:
                # Preserve the source annotation and expose the malformed BIO
                # span for review instead of silently treating it as trusted gold.
                anomalies.append({
                    "kind": "orphan_I",
                    "token_index": index,
                    "token": tokens[index],
                })
                active_start = index
                active_needs_review = True
        elif tag == "O":
            close(index)
        else:
            raise ValueError(f"Unexpected SkillSpan BIO tag: {tag!r}")
    close(len(tokens))
    return spans, anomalies


def read_source_split(path: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row.get("idx"), int) or row.get("source") not in {"house", "tech"}:
            raise ValueError(f"Unexpected document identity on line {line_no} of {path}")
        if not isinstance(row.get("tokens"), list):
            raise ValueError(f"Missing token list on line {line_no} of {path}")
        grouped[(row["source"], row["idx"])].append(row)
    return grouped


def make_document(split_name: str, source: str, upstream_id: int,
                  sentence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    sentence_records = []
    text_parts = []
    gold_skill = []
    gold_knowledge = []
    annotation_anomalies = []
    document_cursor = 0
    token_count = 0

    for sentence_index, row in enumerate(sentence_rows):
        tokens = [str(token) for token in row["tokens"]]
        text = " ".join(tokens)
        skill_spans, skill_anomalies = parse_bio(tokens, row["tags_skill"])
        knowledge_spans, knowledge_anomalies = parse_bio(tokens, row["tags_knowledge"])
        sentence_records.append({
            "sentence_index": sentence_index,
            "text": text,
            "tokens": tokens,
            "gold_skill_spans": skill_spans,
            "gold_knowledge_spans": knowledge_spans,
            "source_tags_skill": row["tags_skill"],
            "source_tags_knowledge": row["tags_knowledge"],
        })
        for tag_name, anomalies in (("Skill", skill_anomalies), ("Knowledge", knowledge_anomalies)):
            for anomaly in anomalies:
                annotation_anomalies.append({
                    **anomaly,
                    "label": tag_name,
                    "sentence_index": sentence_index,
                })
        for label, spans, destination in (
            ("Skill", skill_spans, gold_skill),
            ("Knowledge", knowledge_spans, gold_knowledge),
        ):
            for span in spans:
                destination.append({
                    "start": document_cursor + span["start"],
                    "end_exclusive": document_cursor + span["end_exclusive"],
                    "text": span["text"],
                    "label": label,
                    "sentence_index": sentence_index,
                    "token_start": span["token_start"],
                    "token_end_exclusive": span["token_end_exclusive"],
                    "needs_review": span["needs_review"],
                })
        text_parts.append(text)
        document_cursor += len(text) + (1 if sentence_index + 1 < len(sentence_rows) else 0)
        token_count += len(tokens)

    document_text = "\n".join(text_parts)
    return {
        "job_key": f"skillspan:{split_name}:{source}:{upstream_id}",
        "split": split_name,
        "upstream_split": "dev" if split_name == "validation" else "test",
        "source": source,
        "language": "en",
        "upstream_job_id": upstream_id,
        "text": document_text,
        "sentence_count": len(sentence_records),
        "token_count": token_count,
        "gold_skill_spans": gold_skill,
        "gold_knowledge_spans": gold_knowledge,
        "annotation_anomalies": annotation_anomalies,
        "sentences": sentence_records,
    }


def upstream_revision(source_dir: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    source_data = source_dir / "data/json"
    if not source_data.is_dir():
        raise SystemExit(
            f"Cannot find {source_data}. Clone https://github.com/kris927b/SkillSpan "
            "or pass --source-dir."
        )

    documents_by_split: dict[str, list[dict[str, Any]]] = {}
    for upstream_split, split_name in SPLITS:
        grouped = read_source_split(source_data / f"{upstream_split}.json")
        documents = [
            make_document(split_name, source, upstream_id, rows)
            for (source, upstream_id), rows in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
            if source == "tech"
        ]
        if not documents:
            raise RuntimeError(f"No SkillSpan TECH jobs found in {upstream_split}.json")
        documents_by_split[split_name] = documents

    validation_hashes = {sha256(job["text"]) for job in documents_by_split["validation"]}
    holdout_hashes = {sha256(job["text"]) for job in documents_by_split["holdout"]}
    duplicate_hashes = validation_hashes & holdout_hashes
    if duplicate_hashes:
        raise RuntimeError(f"Found {len(duplicate_hashes)} exact normalized descriptions across dev/test")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for split_name, documents in documents_by_split.items():
        out_path = OUTPUT_DIR / f"{split_name}_tech.json"
        out_path.write_text(
            json.dumps({
                "schema_version": "1.0.0",
                "dataset": "SkillSpan external benchmark",
                "split": split_name,
                "source_filter": "tech",
                "annotation_scope": ["Skill", "Knowledge"],
                "documents": documents,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    manifest_path = OUTPUT_DIR / "split_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "job_key", "split", "upstream_split", "source", "upstream_job_id",
            "language", "sentence_count", "token_count", "gold_skill_spans",
            "gold_knowledge_spans", "normalized_text_sha256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for split_name in ("validation", "holdout"):
            for job in documents_by_split[split_name]:
                writer.writerow({
                    "job_key": job["job_key"],
                    "split": job["split"],
                    "upstream_split": job["upstream_split"],
                    "source": job["source"],
                    "upstream_job_id": job["upstream_job_id"],
                    "language": job["language"],
                    "sentence_count": job["sentence_count"],
                    "token_count": job["token_count"],
                    "gold_skill_spans": len(job["gold_skill_spans"]),
                    "gold_knowledge_spans": len(job["gold_knowledge_spans"]),
                    "normalized_text_sha256": sha256(job["text"]),
                })

    all_docs = [job for docs in documents_by_split.values() for job in docs]
    counts = {}
    anomaly_count = 0
    for split_name, documents in documents_by_split.items():
        anomaly_count += sum(len(job["annotation_anomalies"]) for job in documents)
        counts[split_name] = {
            "jobs": len(documents),
            "sentences": sum(job["sentence_count"] for job in documents),
            "tokens": sum(job["token_count"] for job in documents),
            "gold_skill_spans": sum(len(job["gold_skill_spans"]) for job in documents),
            "gold_knowledge_spans": sum(len(job["gold_knowledge_spans"]) for job in documents),
        }

    report = [
        "# SkillSpan TECH external validation and holdout",
        "",
        "> Separate English, external evaluation set. Do not merge its scores with the 14-job Saramin benchmark.",
        "",
        "## Split and annotation",
        "",
        f"- Upstream revision: `{upstream_revision(source_dir)}`.",
        "- Validation comes only from upstream `dev.json`; holdout comes only from upstream `test.json`.",
        "- Kept only `source=tech` and grouped all sentences by the upstream job ID before assigning each posting to one split.",
        f"- Exact normalized-description overlap between validation and holdout: `{len(duplicate_hashes)}`.",
        "- Counts below are measured from the pinned JSON files. The paper's table reports 30 TECH dev jobs and 32 TECH test jobs, while this repository revision contains 29 and 31 respectively; the split manifest records the actual evaluated IDs.",
        "- The SkillSpan paper reports expert span annotations and describes the test split as annotated by three annotators with majority-vote aggregation. The validation split was annotated by one annotator.",
        f"- Source BIO anomalies detected: `{anomaly_count}`. An orphan `I` is retained as a provisional span marked `needs_review=true`; source tag arrays are preserved. It is not part of the primary Knowledge metric.",
        "- This is not the project's six-label Vietnamese gold. For the project's technical entity extraction, compare the union of its six predicted labels to SkillSpan `Knowledge` spans; keep SkillSpan `Skill` spans available for separate analysis, not as negatives.",
        "",
        "## Dataset size",
        "",
        "| Split | Jobs | Sentences | Tokens | Skill spans | Knowledge spans |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split_name in ("validation", "holdout"):
        values = counts[split_name]
        report.append(
            f"| {split_name} | {values['jobs']} | {values['sentences']} | {values['tokens']} | "
            f"{values['gold_skill_spans']} | {values['gold_knowledge_spans']} |"
        )
    report += [
        "",
        "## Use",
        "",
        "1. Use validation to compare checkpoints and thresholds.",
        "2. Keep holdout frozen until the model and threshold are selected; report it once for final comparison.",
        "3. Do not use either split for fine-tuning or training negatives.",
        "4. Keep the original internal Saramin split for Vietnamese evaluation. This external English set measures cross-source and cross-language transfer, not MVP performance on Vietnamese postings.",
        "",
        "## Provenance and attribution",
        "",
        "- Dataset: [SkillSpan repository](https://github.com/kris927b/SkillSpan), converted from the released JSON sentence annotations.",
        "- Paper: Zhang et al. (2022), [SkillSpan: Hard and Soft Skill Extraction from English Job Postings](https://aclanthology.org/2022.naacl-main.366/).",
        "- The paper identifies the TECH source as Stack Overflow job postings licensed under CC BY-SA. Stack Overflow states contributions from 2018-05-02 onward use CC BY-SA 4.0; assigning version 4.0 to this 2020-2021 sample is based on source/date, not post-level license metadata. Retain attribution and ShareAlike terms when redistributing derived text.",
        "- [Stack Overflow licensing information](https://stackoverflow.com/help/licensing).",
        "- The original repository's MIT license covers its software; dataset licensing is source-specific and documented in the paper/data statement.",
        "",
        "## Files",
        "",
        "- `validation_tech.json`: postings reconstructed from all released sentence rows and exact Skill/Knowledge spans from upstream dev.",
        "- `holdout_tech.json`: postings reconstructed from all released sentence rows and exact Skill/Knowledge spans from upstream test.",
        "- `split_manifest.csv`: one row per posting, with split, annotation counts, and normalized text hash.",
        "",
        "## Reproduce",
        "",
        "```powershell",
        "git clone --depth 1 https://github.com/kris927b/SkillSpan.git .tmp/skillspan_source",
        ".venv\\Scripts\\python.exe scripts\\prepare_skillspan_external_benchmark.py",
        ".venv\\Scripts\\python.exe scripts\\evaluate_skillspan_external.py --threshold 0.40",
        "```",
        "",
    ]
    metrics_path = OUTPUT_DIR / "gliner_baseline_040.json"
    if metrics_path.exists():
        metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
        report += [
            "## Initial GLiNER baseline",
            "",
            f"- Checkpoint: `{metrics_data['model']}`; threshold `{metrics_data['threshold']:.2f}`; exact character-span matching.",
            "- This is a fixed-threshold baseline, not a threshold sweep. Holdout has been evaluated once and should remain frozen while selecting later checkpoints on validation.",
            "",
            "| Split | Jobs | Precision | Recall | F1 | TP | FP | FN |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for split_name in ("validation", "holdout"):
            values = metrics_data["results"][split_name]
            report.append(
                f"| {split_name} | {values['jobs']} | {values['precision']:.3f} | "
                f"{values['recall']:.3f} | {values['f1']:.3f} | {values['tp']} | "
                f"{values['fp']} | {values['fn']} |"
            )
        report += ["", ""]
    (OUTPUT_DIR / "README.md").write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({
        "source_revision": upstream_revision(source_dir),
        "counts": counts,
        "exact_duplicate_descriptions_across_splits": len(duplicate_hashes),
        "outputs": [
            str((OUTPUT_DIR / "validation_tech.json").relative_to(ROOT)),
            str((OUTPUT_DIR / "holdout_tech.json").relative_to(ROOT)),
            str(manifest_path.relative_to(ROOT)),
            str((OUTPUT_DIR / "README.md").relative_to(ROOT)),
        ],
        "total_documents": len(all_docs),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
