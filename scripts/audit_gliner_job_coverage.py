"""Find GLiNER skill candidates missing from the current per-job review.

This script only proposes spans. It does not turn model predictions into gold
labels or training negatives; a separate AI/human adjudication pass is needed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch
from gliner import GLiNER

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data/staging/saramin/embedded_jobs_2026-11-09.json"
AI_REVIEW_PATH = ROOT / "data/gliner_finetune_ai_review.csv"
OUTPUT_ALL = ROOT / "data/gliner_job_coverage_predictions.csv"
OUTPUT_NEW = ROOT / "data/gliner_job_coverage_candidates.csv"
MODEL_ID = "urchade/gliner_multi-v2.1"
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


def normalized(value: str) -> str:
    import unicodedata

    folded = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in folded if character.isalnum())


def make_chunks(text: str):
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            cut = max(text.rfind("\n", start + int(CHUNK_SIZE * 0.7), end),
                      text.rfind(" ", start + int(CHUNK_SIZE * 0.7), end))
            if cut > start:
                end = cut
        yield start, end, text[start:end]
        if end == len(text):
            break
        next_start = max(start + 1, end - CHUNK_OVERLAP)
        while next_start < end and not text[next_start].isspace():
            next_start += 1
        start = next_start


def context(text: str, start: int, end: int, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def read_confirmed_spans():
    spans = defaultdict(list)
    with AI_REVIEW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("ai_decision") not in {"approve_positive", "repair_positive"}:
                continue
            jid = str(row["job_id"])
            section = row.get("ai_approved_section", "")
            surface = row.get("ai_approved_surface", "")
            label = row.get("ai_approved_gliner_label", "")
            if jid and section and surface and label:
                try:
                    start = int(row["span_start_char"])
                    end = int(row["span_end_char_exclusive"])
                except (KeyError, TypeError, ValueError):
                    continue
                spans[(jid, section)].append((start, end, label, surface))
    return spans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.15,
                        help="Low proposal threshold; rows also report whether they meet 0.40.")
    args = parser.parse_args()

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    jobs = {str(job["id"]): job for job in raw["jobs"]}
    reviewed = read_confirmed_spans()

    chunks = []
    sources = {}
    for jid, job in jobs.items():
        for section in ("requirements", "responsibilities"):
            text = job.get(section + "_text") or ""
            sources[(jid, section)] = text
            for start, end, part in make_chunks(text):
                chunks.append({"job_id": jid, "section": section, "start": start,
                               "end": end, "text": part})

    print(f"Jobs: {len(jobs)}; source sections: {sum(bool(t) for t in sources.values())}; chunks: {len(chunks)}")
    print(f"Loading {MODEL_ID}; proposal threshold={args.threshold:.2f}")
    model = GLiNER.from_pretrained(MODEL_ID).to("cuda" if torch.cuda.is_available() else "cpu").eval()
    raw_predictions = []
    with torch.inference_mode():
        for base in range(0, len(chunks), 8):
            batch = chunks[base:base + 8]
            predictions = model.inference([item["text"] for item in batch], LABELS,
                                          threshold=args.threshold, batch_size=8)
            for chunk, entities in zip(batch, predictions):
                for entity in entities:
                    start = chunk["start"] + int(entity["start"])
                    end = chunk["start"] + int(entity["end"])
                    raw_predictions.append({
                        "job_id": chunk["job_id"],
                        "section": chunk["section"],
                        "start": start,
                        "end": end,
                        "surface": entity.get("text", ""),
                        "label": entity.get("label", ""),
                        "score": float(entity.get("score", 0.0)),
                    })

    # Merge overlapping-window duplicates by exact source offsets and label.
    merged = {}
    for row in raw_predictions:
        key = (row["job_id"], row["section"], row["start"], row["end"], row["label"])
        if key not in merged or row["score"] > merged[key]["score"]:
            merged[key] = row

    rows_all = []
    rows_new = []
    counts = Counter()
    for row in merged.values():
        source = sources[(row["job_id"], row["section"])]
        row["surface"] = source[row["start"]:row["end"]]
        approved = reviewed[(row["job_id"], row["section"])]
        overlapping = [
            item for item in approved
            if row["start"] < item[1] and item[0] < row["end"]
        ]
        exact = [item for item in overlapping if row["start"] == item[0] and row["end"] == item[1]]
        matched = bool(overlapping)
        label_conflict = any(item[2] != row["label"] for item in exact)
        reviewed_surfaces = " | ".join(sorted({item[3] for item in overlapping}))
        output = {
            "job_id": row["job_id"],
            "job_title": jobs[row["job_id"]].get("title", ""),
            "section": row["section"],
            "start_char": row["start"],
            "end_char_exclusive": row["end"],
            "surface": row["surface"],
            "proposed_gliner_label": row["label"],
            "score": f"{row['score']:.4f}",
            "at_or_above_040": row["score"] >= 0.4,
            "covered_by_ai_review": matched,
            "review_match": "exact" if exact else "overlap" if overlapping else "new_span",
            "reviewed_surface": reviewed_surfaces,
            "label_conflict": label_conflict,
            "context": context(source, row["start"], row["end"]),
            "human_decision": "",
            "approved_skill": "",
            "approved_gliner_label": "",
            "notes": "",
        }
        rows_all.append(output)
        counts[(row["job_id"], row["section"], "all")] += 1
        if not matched:
            rows_new.append(output)
            counts[(row["job_id"], row["section"], "new")] += 1

    fields = list(rows_all[0]) if rows_all else []
    for path, data in ((OUTPUT_ALL, rows_all), (OUTPUT_NEW, rows_new)):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)

    print(f"Deduplicated proposals: {len(rows_all)}; not yet covered by AI review: {len(rows_new)}")
    print("Review match types:", dict(Counter(row["review_match"] for row in rows_all)))
    print("Exact-span label conflicts:", sum(bool(row["label_conflict"]) for row in rows_all))
    print("Per-job/section new proposals:")
    for jid in jobs:
        for section in ("requirements", "responsibilities"):
            n = counts[(jid, section, "new")]
            if n:
                title = jobs[jid].get("title", "")
                print(f"  {jid} | {section} | {n:3} | {title}")
    print(f"Wrote {OUTPUT_ALL}")
    print(f"Wrote {OUTPUT_NEW}")


if __name__ == "__main__":
    main()
