"""Evaluate GLiNER on the frozen SkillSpan TECH validation/holdout sets.

The six project labels are collapsed to a single technical-entity class and
scored against SkillSpan Knowledge spans. Skill spans are retained in the
source data but are not treated as negatives for this evaluation.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
from gliner import GLiNER


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/skillspan_external"
DEFAULT_MODEL = "urchade/gliner_multi-v2.1"
LABELS = [
    "programming language",
    "software framework or library",
    "database or query technology",
    "cloud or data platform",
    "software development or testing tool",
    "technical method, protocol, or architecture",
]
CHUNK_SIZE = 850
CHUNK_OVERLAP = 140


def make_chunks(text: str):
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            cut = max(
                text.rfind("\n", start + int(CHUNK_SIZE * 0.7), end),
                text.rfind(" ", start + int(CHUNK_SIZE * 0.7), end),
            )
            if cut > start:
                end = cut
        yield start, end, text[start:end]
        if end == len(text):
            break
        next_start = max(start + 1, end - CHUNK_OVERLAP)
        while next_start < end and not text[next_start].isspace():
            next_start += 1
        start = next_start


def metrics(gold: set[tuple[int, int]], predicted: set[tuple[int, int]]) -> dict[str, Any]:
    tp = len(gold & predicted)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "gold": len(gold),
        "predicted": len(predicted),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def load_documents(split: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{split}_tech.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("split") != split:
        raise ValueError(f"Wrong split in {path}")
    return data["documents"]


def evaluate_split(model, documents: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    chunks = []
    by_job: dict[str, dict[str, Any]] = {}
    for document in documents:
        job_key = document["job_key"]
        by_job[job_key] = document
        for start, end, text in make_chunks(document["text"]):
            chunks.append({"job_key": job_key, "start": start, "end": end, "text": text})

    raw_predictions: dict[str, dict[tuple[int, int], float]] = defaultdict(dict)
    with torch.inference_mode():
        for offset in range(0, len(chunks), 8):
            batch = chunks[offset:offset + 8]
            output = model.inference(
                [item["text"] for item in batch],
                LABELS,
                threshold=threshold,
                batch_size=8,
            )
            for chunk, entities in zip(batch, output):
                for entity in entities:
                    span = (
                        chunk["start"] + int(entity["start"]),
                        chunk["start"] + int(entity["end"]),
                    )
                    score = float(entity.get("score", 0.0))
                    raw_predictions[chunk["job_key"]][span] = max(
                        score, raw_predictions[chunk["job_key"]].get(span, 0.0)
                    )

    total_gold: set[tuple[str, int, int]] = set()
    total_predicted: set[tuple[str, int, int]] = set()
    per_job = []
    for job_key, document in by_job.items():
        gold = {
            (int(span["start"]), int(span["end_exclusive"]))
            for span in document["gold_knowledge_spans"]
            if not span.get("needs_review", False)
        }
        predicted = set(raw_predictions.get(job_key, {}))
        total_gold.update((job_key, start, end) for start, end in gold)
        total_predicted.update((job_key, start, end) for start, end in predicted)
        per_job.append({"job_key": job_key, **metrics(gold, predicted)})

    tp = len(total_gold & total_predicted)
    fp = len(total_predicted - total_gold)
    fn = len(total_gold - total_predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    macro_recall = sum(row["recall"] for row in per_job if row["gold"] > 0) / max(
        1, sum(row["gold"] > 0 for row in per_job)
    )
    return {
        "jobs": len(documents),
        "chunks": len(chunks),
        "gold_knowledge_spans": len(total_gold),
        "predicted_spans": len(total_predicted),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "macro_recall": macro_recall,
        "per_job": per_job,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--threshold", type=float, default=0.40)
    parser.add_argument("--output", type=Path, default=DATA_DIR / "gliner_baseline_040.json")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {args.model} on {device}; threshold={args.threshold:.2f}")
    model = GLiNER.from_pretrained(args.model).to(device).eval()
    results = {
        "schema_version": "1.0.0",
        "model": args.model,
        "threshold": args.threshold,
        "device": device,
        "prediction_scope": LABELS,
        "gold_scope": "SkillSpan Knowledge spans; exact character boundaries; Skill spans excluded from negatives.",
        "results": {},
    }
    for split in ("validation", "holdout"):
        documents = load_documents(split)
        print(f"Evaluating {split}: {len(documents)} jobs")
        results["results"][split] = evaluate_split(model, documents, args.threshold)
        summary = results["results"][split]
        print(
            f"{split}: P={summary['precision']:.3f} R={summary['recall']:.3f} "
            f"F1={summary['f1']:.3f} TP={summary['tp']} FP={summary['fp']} FN={summary['fn']}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
