"""Run a GLiNER fine-tuning pilot using AI-reviewed first-pass labels.

AI review is not human annotation. Validation/holdout still use the existing
draft benchmark, so the resulting metrics are exploratory only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import random
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
from gliner import GLiNER


ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "urchade/gliner_multi-v2.1"
BENCHMARK_PATH = ROOT / "web/static/data/skill_benchmark_v0.json"
RAW_JOBS_PATH = ROOT / "data/staging/saramin/embedded_jobs_2026-11-09.json"
FILTERED_SKILLS_PATH = ROOT / "data/skill_benchmark_gliner_label_filtered.md"
REVIEW_QUEUE_PATH = ROOT / "data/gliner_finetune_review_queue.csv"
AI_REVIEW_PATH = ROOT / "data/gliner_finetune_ai_review.csv"
COVERAGE_REVIEW_PATH = ROOT / "data/gliner_job_coverage_ai_review.csv"
OUTPUT_DIR = ROOT / ".tmp/gliner_finetune_pilot"
REPORT_PATH = ROOT / "data/gliner_finetune_pilot_report.md"
EXTERNAL_METRICS_PATH = ROOT / "data/skillspan_external/gliner_baseline_040.json"

LABELS = [
    "programming language",
    "software framework or library",
    "database or query technology",
    "cloud or data platform",
    "software development or testing tool",
    "technical method, protocol, or architecture",
]
HOLDOUT_IDS = {"2144686", "2143927", "2139328", "2141955"}
VALIDATION_IDS = {"2143923", "2138202"}
TRAIN_STEPS = 80
SEED = 41
CHUNK_SIZE = 850
CHUNK_OVERLAP = 140


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_filtered_skills() -> set[str]:
    return {
        line[2:].strip().casefold()
        for line in FILTERED_SKILLS_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("- ")
    }


def terms(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def section_names(value: Any, default_both: bool = False) -> list[str]:
    allowed = {"requirements", "responsibilities"}
    if isinstance(value, list):
        result = [name for name in value if name in allowed]
    elif isinstance(value, str):
        result = [name for name in allowed if re.search(rf"\b{name}\b", value, re.I)]
    else:
        result = []
    return result or (sorted(allowed) if default_both else [])


def find_spans(text: str, variants: list[str]) -> list[tuple[int, int, str]]:
    matches: dict[tuple[int, int], str] = {}
    for variant in variants:
        if not variant:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(variant)}(?!\w)", re.I)
        for match in pattern.finditer(text):
            matches[(match.start(), match.end())] = text[match.start():match.end()]
    return [(start, end, surface) for (start, end), surface in sorted(matches.items())]


def make_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            # Prefer a nearby line or word boundary so we do not split skill spans.
            cut = max(text.rfind("\n", start + int(size * 0.7), end), text.rfind(" ", start + int(size * 0.7), end))
            if cut > start:
                end = cut
        yield start, end, text[start:end]
        if end == len(text):
            break
        next_start = max(start + 1, end - overlap)
        while next_start < end and not text[next_start].isspace():
            next_start += 1
        start = next_start


def make_train_chunks(text: str, size: int = 500):
    """Pack complete source lines into shorter, non-overlapping training samples."""
    line_spans = []
    offset = 0
    for line in text.splitlines(keepends=True):
        line_spans.append((offset, offset + len(line), line))
        offset += len(line)
    if offset < len(text):
        line_spans.append((offset, len(text), text[offset:]))

    packed_start = None
    packed_end = None
    packed_text = ""
    for start, end, line in line_spans:
        if len(line) > size:
            if packed_start is not None:
                yield packed_start, packed_end, packed_text
                packed_start, packed_end, packed_text = None, None, ""
            for sub_start, sub_end, part in make_chunks(line, size=size, overlap=0):
                yield start + sub_start, start + sub_end, part
            continue
        if packed_start is not None and end - packed_start > size:
            yield packed_start, packed_end, packed_text
            packed_start, packed_end, packed_text = start, end, line
        elif packed_start is None:
            packed_start, packed_end, packed_text = start, end, line
        else:
            packed_end = end
            packed_text += line
    if packed_start is not None:
        yield packed_start, packed_end, packed_text


def split_name(job_id: str) -> str:
    if job_id in HOLDOUT_IDS:
        return "holdout_eval"
    if job_id in VALIDATION_IDS:
        return "validation"
    return "train"


def get_label_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(label) for label in value if str(label) in LABELS]
    if isinstance(value, str):
        return [label for label in value.split(" | ") if label in LABELS]
    return []


def normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in folded if character.isalnum())


def build_sources_and_gold(benchmark, raw_jobs, filtered):
    sources: dict[tuple[str, str], str] = {}
    gold_by_job: dict[str, dict[str, set[str]]] = defaultdict(dict)
    found_specs = []
    missed_specs = []
    extra_specs = []
    skill_labels: dict[str, Counter[str]] = defaultdict(Counter)

    for row in benchmark["rows"]:
        job_id = str(row["job_id"])
        raw = raw_jobs[job_id]
        for section, field in (("requirements", "requirements_text"), ("responsibilities", "responsibilities_text")):
            sources[(job_id, section)] = raw.get(field) or ""

        for item in row.get("found", []):
            skill = item["skill"]
            if skill.casefold() not in filtered:
                continue
            # model_surface was the actual detected text mapped to this gold
            # concept in the source benchmark, so it is an accepted alias for
            # the existing exact-match evaluation.
            variants = terms(item.get("gold_variants")) + terms(item.get("model_surface")) + [skill]
            key = normalized(skill)
            gold_by_job[job_id].setdefault(key, set()).update(normalized(v) for v in variants if normalized(v))
            labs = get_label_list(item.get("labels"))
            if labs:
                skill_labels[key].update(labs)
            found_specs.append({"job_id": job_id, "skill": skill, "variants": variants,
                                "sections": section_names(item.get("sections"), True), "labels": labs})

        for item in row.get("missed", []):
            skill = item["skill"]
            if skill.casefold() not in filtered:
                continue
            variants = terms(item.get("gold_variants")) + [skill]
            key = normalized(skill)
            gold_by_job[job_id].setdefault(key, set()).update(normalized(v) for v in variants if normalized(v))
            missed_specs.append({"job_id": job_id, "skill": skill, "variants": variants,
                                 "sections": ["requirements", "responsibilities"], "labels": []})

        for item in row.get("extras", []):
            extra_specs.append({"job_id": job_id, "skill": item["skill"],
                                "variants": terms(item.get("surface_forms")) + [item["skill"]],
                                "sections": section_names(item.get("sections"), True)})

    return sources, gold_by_job, found_specs, missed_specs, extra_specs, skill_labels


def make_candidate_maps(sources, found_specs, missed_specs, extra_specs, skill_labels):
    labelled_spans: dict[tuple[str, str, int, int], set[str]] = defaultdict(set)
    unresolved_spans: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)
    extra_spans: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)

    def spans_for_spec(text, spec):
        if spec.get("start_char") is not None and spec.get("end_char") is not None:
            start, end = int(spec["start_char"]), int(spec["end_char"])
            expected = spec.get("surface", "")
            if 0 <= start < end <= len(text) and (not expected or text[start:end] == expected):
                return [(start, end, text[start:end])]
            raise ValueError(f"Review span does not match source text: {spec}")
        return find_spans(text, spec["variants"])

    for spec in found_specs:
        for section in spec["sections"]:
            text = sources[(spec["job_id"], section)]
            for start, end, _ in spans_for_spec(text, spec):
                labelled_spans[(spec["job_id"], section, start, end)].update(spec["labels"])

    for spec in missed_specs:
        for section in spec["sections"]:
            text = sources[(spec["job_id"], section)]
            for start, end, _ in spans_for_spec(text, spec):
                # A label inferred from another benchmark occurrence of the same
                # skill is weak supervision, not a human-approved class.
                labels = skill_labels.get(normalized(spec["skill"]), Counter())
                if labels:
                    label = labels.most_common(1)[0][0]
                    labelled_spans[(spec["job_id"], section, start, end)].add(label)
                else:
                    unresolved_spans[(spec["job_id"], section)].add((start, end))

    for spec in extra_specs:
        for section in spec["sections"]:
            text = sources[(spec["job_id"], section)]
            for start, end, _ in spans_for_spec(text, spec):
                extra_spans[(spec["job_id"], section)].add((start, end))

    return labelled_spans, unresolved_spans, extra_spans


def infer_low_threshold_labels(model, chunks):
    texts = [item["text"] for item in chunks]
    low_labels: dict[tuple[str, str, int, int], Counter[str]] = defaultdict(Counter)
    for base in range(0, len(texts), 8):
        batch = texts[base:base + 8]
        with torch.inference_mode():
            predictions = model.inference(batch, LABELS, threshold=0.05, batch_size=8)
        for chunk, entities in zip(chunks[base:base + 8], predictions):
            for entity in entities:
                start = chunk["start"] + int(entity["start"])
                end = chunk["start"] + int(entity["end"])
                if entity["label"] in LABELS:
                    low_labels[(chunk["job_id"], chunk["section"], start, end)][entity["label"]] += float(entity["score"])
    return low_labels


def build_ai_review_specs(review_rows, coverage_rows=()):
    found_specs = []
    unresolved_specs = []
    extra_specs = []
    excluded_sections = set()
    counts = Counter(row["ai_decision"] for row in review_rows)

    for row in review_rows:
        job_id = str(row["job_id"])
        section = row.get("ai_approved_section") or row.get("source_section") or ""
        decision = row["ai_decision"]
        surface = row.get("ai_approved_surface") or row.get("source_surface") or ""
        if decision in {"approve_positive", "repair_positive"}:
            label = row.get("ai_approved_gliner_label", "")
            if label not in LABELS or not surface or section not in {"requirements", "responsibilities"}:
                continue
            found_specs.append({
                "job_id": job_id,
                "skill": row.get("ai_approved_skill") or row["candidate_skill"],
                "variants": [surface],
                "sections": [section],
                "labels": [label],
                "start_char": int(row["span_start_char"]) if row.get("span_start_char") else None,
                "end_char": int(row["span_end_char_exclusive"]) if row.get("span_end_char_exclusive") else None,
                "surface": surface,
            })
        elif decision in {"needs_label", "needs_review"} and surface and section in {"requirements", "responsibilities"}:
            # Do not turn a located but unclassified skill candidate into a
            # negative training span. Chunks containing one are excluded.
            unresolved_specs.append({"job_id": job_id, "skill": row["candidate_skill"],
                                     "variants": [surface], "sections": [section], "labels": [],
                                     "start_char": int(row["span_start_char"]) if row.get("span_start_char") else None,
                                     "end_char": int(row["span_end_char_exclusive"]) if row.get("span_end_char_exclusive") else None,
                                     "surface": surface})
        elif decision in {"reject_background", "out_of_scope"} and surface and section in {"requirements", "responsibilities"}:
            extra_specs.append({"job_id": job_id, "skill": row["candidate_skill"],
                                "variants": [surface], "sections": [section],
                                "start_char": int(row["span_start_char"]) if row.get("span_start_char") else None,
                                "end_char": int(row["span_end_char_exclusive"]) if row.get("span_end_char_exclusive") else None,
                                "surface": surface})
        elif decision == "needs_span" and split_name(job_id) == "train":
            # We cannot verify where this candidate occurs, so avoid using any
            # training chunks from that source section as unlabeled background.
            source_section = row.get("source_section", "")
            if source_section in {"requirements", "responsibilities"}:
                excluded_sections.add((job_id, source_section))

    coverage_counts = Counter(row.get("ai_decision", "") for row in coverage_rows)
    counts.update({f"coverage:{decision}": count for decision, count in coverage_counts.items()})
    for row in coverage_rows:
        job_id = str(row["job_id"])
        section = row.get("human_approved_section") or row.get("section", "")
        surface = row.get("human_approved_surface") or row.get("surface", "")
        decision = row.get("human_decision") or row.get("ai_decision", "")
        approved_skill = row.get("human_approved_skill") or row.get("approved_skill") or surface
        approved_label = row.get("human_approved_gliner_label") or row.get("approved_gliner_label", "")
        try:
            start = int(row["start_char"])
            end = int(row["end_char_exclusive"])
        except (KeyError, TypeError, ValueError):
            start = end = None
        if not surface or section not in {"requirements", "responsibilities"}:
            continue
        spec = {"job_id": job_id, "skill": approved_skill,
                "variants": [surface], "sections": [section], "surface": surface,
                "start_char": start, "end_char": end}
        if decision in {"approve_positive", "approve_repeat_positive", "repair", "repair_positive"}:
            label = approved_label
            if label in LABELS:
                spec["labels"] = [label]
                found_specs.append(spec)
        elif decision in {"needs_review", "needs_span", "needs_label"}:
            spec["labels"] = []
            unresolved_specs.append(spec)
        elif decision in {"reject_background", "out_of_scope"}:
            extra_specs.append(spec)

    return found_specs, unresolved_specs, extra_specs, excluded_sections, counts


def build_examples(model, sources, found_specs, unresolved_specs, extra_specs, excluded_sections):
    training_chunks = []
    for (job_id, section), text in sources.items():
        for start, end, part in make_train_chunks(text):
            training_chunks.append({"job_id": job_id, "section": section, "start": start, "end": end, "text": part})
    labelled_spans, unresolved_spans, extra_spans = make_candidate_maps(
        sources, found_specs, unresolved_specs, extra_specs, {}
    )

    examples_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_ambiguous = 0
    skipped_unaligned = 0
    for chunk in training_chunks:
        jid, section = chunk["job_id"], chunk["section"]
        cs, ce, text = chunk["start"], chunk["end"], chunk["text"]
        if split_name(jid) == "train" and (jid, section) in excluded_sections:
            continue
        # Do not teach the model that a known, unresolved gold candidate is
        # background. The whole overlapping chunk is excluded from this pilot.
        if any(cs <= start < ce or cs < end <= ce for start, end in unresolved_spans[(jid, section)]):
            skipped_ambiguous += 1
            continue

        selected: list[tuple[int, int, str]] = []
        for (span_job, span_section, start, end), labels in labelled_spans.items():
            if span_job == jid and span_section == section and cs <= start and end <= ce:
                selected.extend((start - cs, end - cs, label) for label in sorted(labels))

        has_extra = any(cs <= start and end <= ce for start, end in extra_spans[(jid, section)])
        if not selected and not has_extra:
            continue

        token_offsets = list(model.data_processor.words_splitter(text))
        tokens = [token for token, _, _ in token_offsets]
        if not tokens or len(tokens) > int(model.config.max_len):
            skipped_unaligned += 1
            continue
        start_to_word = {start: idx for idx, (_, start, _) in enumerate(token_offsets)}
        end_to_word = {end: idx for idx, (_, _, end) in enumerate(token_offsets)}
        ner = []
        for start, end, label in selected:
            word_start = start_to_word.get(start)
            word_end = end_to_word.get(end)
            if word_start is None or word_end is None:
                skipped_unaligned += 1
                continue
            ner.append([word_start, word_end, label])
        # Deduplicate identical spans and labels, including overlapping source
        # mentions repeated across chunk windows.
        ner = [list(item) for item in sorted({tuple(item) for item in ner})]
        examples_by_split[split_name(jid)].append({"tokenized_text": tokens, "ner": ner})

    all_train_types = sorted({span[2] for sample in examples_by_split["train"] for span in sample["ner"]})
    for split, samples in examples_by_split.items():
        for sample in samples:
            sample["_job_split"] = split
    return examples_by_split, all_train_types, skipped_ambiguous, skipped_unaligned, {}


def add_negative_type_samples(samples, train_types, ratio, seed):
    rng = random.Random(seed)
    prepared = []
    for sample in samples:
        result = {"tokenized_text": sample["tokenized_text"], "ner": sample["ner"]}
        positive = {span[2] for span in result["ner"]}
        eligible = [label for label in train_types if label not in positive]
        count = int(round(len(eligible) * ratio))
        result["ner_negatives"] = sorted(rng.sample(eligible, count)) if count else []
        prepared.append(result)
    return prepared


def eval_metrics(model, sources, gold_by_job, job_ids, threshold=0.4):
    chunk_rows = []
    for job_id in sorted(job_ids):
        for section in ("requirements", "responsibilities"):
            text = sources.get((job_id, section), "")
            for start, end, part in make_chunks(text):
                chunk_rows.append({"job_id": job_id, "section": section, "start": start, "end": end, "text": part})

    predictions_by_job: dict[str, set[str]] = defaultdict(set)
    with torch.inference_mode():
        for base in range(0, len(chunk_rows), 8):
            batch_chunks = chunk_rows[base:base + 8]
            output = model.inference([item["text"] for item in batch_chunks], LABELS,
                                     threshold=threshold, batch_size=8)
            for chunk, entities in zip(batch_chunks, output):
                for entity in entities:
                    value = normalized(entity.get("text", ""))
                    if value:
                        predictions_by_job[chunk["job_id"]].add(value)

    tp = fp = fn = 0
    for job_id in job_ids:
        candidates = list(gold_by_job.get(job_id, {}).values())
        unmatched = set(range(len(candidates)))
        pred_values = predictions_by_job.get(job_id, set())
        for prediction in sorted(pred_values):
            matches = [idx for idx in unmatched if prediction in candidates[idx]]
            if matches:
                unmatched.remove(matches[0])
                tp += 1
            else:
                fp += 1
        fn += len(unmatched)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def format_metric(row):
    return f"P={row['precision']:.3f}, R={row['recall']:.3f}, F1={row['f1']:.3f} (TP={row['tp']}, FP={row['fp']}, FN={row['fn']})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=TRAIN_STEPS)
    args = parser.parse_args()

    benchmark = load_json(BENCHMARK_PATH)
    raw = load_json(RAW_JOBS_PATH)
    raw_jobs = {str(job["id"]): job for job in raw["jobs"]}
    filtered = load_filtered_skills()
    sources, gold_by_job, _, _, _, _ = build_sources_and_gold(
        benchmark, raw_jobs, filtered
    )
    review_rows = list(csv.DictReader(AI_REVIEW_PATH.open(encoding="utf-8-sig", newline="")))
    coverage_rows = list(csv.DictReader(COVERAGE_REVIEW_PATH.open(encoding="utf-8-sig", newline=""))) if COVERAGE_REVIEW_PATH.exists() else []
    found_specs, unresolved_specs, extra_specs, excluded_sections, review_counts = build_ai_review_specs(review_rows, coverage_rows)
    eval_ids = {"validation": VALIDATION_IDS, "holdout_eval": HOLDOUT_IDS}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading base checkpoint {MODEL_ID} for baseline and token alignment")
    teacher = GLiNER.from_pretrained(MODEL_ID).to("cuda").eval()
    examples, train_types, skipped_ambiguous, skipped_unaligned, _ = build_examples(
        teacher, sources, found_specs, unresolved_specs, extra_specs, excluded_sections
    )
    print("AI review decisions:", dict(review_counts))
    print("AI-reviewed positive spans:", len(found_specs),
          "unresolved review sections skipped from train:", len(excluded_sections))
    print("Examples by split:", {key: len(value) for key, value in examples.items()})
    print("Labels represented in train:", train_types)
    print("Chunks skipped for located but unclassified spans:", skipped_ambiguous,
          "unaligned/too long:", skipped_unaligned)

    baseline = {
        name: eval_metrics(teacher, sources, gold_by_job, ids)
        for name, ids in eval_ids.items()
    }
    print("Baseline:", {name: format_metric(metric) for name, metric in baseline.items()})
    del teacher
    torch.cuda.empty_cache()

    train_examples = examples.get("train", [])
    validation_examples = examples.get("validation", [])
    if len(train_examples) < 4 or not train_types:
        raise RuntimeError("Too few AI-reviewed training examples to run the pilot.")
    if not validation_examples:
        raise RuntimeError("No AI-reviewed validation examples survived filtering.")

    results = []
    best_validation_f1 = -1.0
    best_ratio = None
    best_model = None
    for ratio in (0.0, 0.5, 0.75):
        print(f"\nTraining negative-type ratio={ratio:.2f}, steps={args.steps}")
        random.seed(SEED)
        torch.manual_seed(SEED)
        torch.cuda.manual_seed_all(SEED)
        train_data = add_negative_type_samples(train_examples, train_types, ratio, SEED)
        model = GLiNER.from_pretrained(MODEL_ID)
        trainer = model.train_model(
            train_dataset=train_data,
            eval_dataset=None,
            output_dir=str(OUTPUT_DIR / f"run_{int(ratio * 100):02d}"),
            max_steps=args.steps,
            learning_rate=1e-5,
            others_lr=5e-5,
            weight_decay=0.01,
            others_weight_decay=0.01,
            lr_scheduler_type="cosine",
            warmup_ratio=0.1,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=2,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            save_strategy="no",
            report_to="none",
            dataloader_num_workers=0,
            negatives=1.0,
            masking="none",
        )
        fitted_model = trainer.model.to("cuda").eval()
        validation = eval_metrics(fitted_model, sources, gold_by_job, eval_ids["validation"])
        holdout = eval_metrics(fitted_model, sources, gold_by_job, eval_ids["holdout_eval"])
        results.append({"ratio": ratio, "validation": validation, "holdout": holdout})
        print("Validation:", format_metric(validation))
        print("Holdout:", format_metric(holdout))

        if validation["f1"] > best_validation_f1:
            best_validation_f1 = validation["f1"]
            best_ratio = ratio
            if best_model is not None:
                del best_model
            best_model = fitted_model.to("cpu")
        del trainer, model, fitted_model, train_data
        torch.cuda.empty_cache()

    best_finetuned_ratio = best_ratio
    best_finetuned_validation_f1 = best_validation_f1
    baseline_selected = baseline["validation"]["f1"] >= best_validation_f1
    if baseline_selected:
        del best_model
        best_model = GLiNER.from_pretrained(MODEL_ID)
        best_ratio = None

    best_dir = OUTPUT_DIR / "selected_by_validation"
    best_model.save_pretrained(best_dir)
    shutil.copy2(BENCHMARK_PATH, OUTPUT_DIR / "source_benchmark.json")
    del best_model
    torch.cuda.empty_cache()

    report = [
        "# GLiNER fine-tuning pilot (AI first-pass review)",
        "",
        "> **Kết quả thăm dò, chưa phải đánh giá chuẩn.** Train annotations do Codex AI rà soát từ candidate queue; đây không phải nhãn do con người xác nhận. Validation/holdout vẫn được chấm theo benchmark nháp hiện có.",
        "",
        f"- Checkpoint: `{MODEL_ID}`",
        f"- Runtime: GLiNER `{importlib.metadata.version('gliner')}`, PyTorch `{torch.__version__}`, Transformers `{importlib.metadata.version('transformers')}`, CUDA `{torch.version.cuda}` on `{torch.cuda.get_device_name(0)}`.",
        f"- Seed: `{SEED}`; steps mỗi cấu hình: `{args.steps}`; ngưỡng đánh giá: `0.40`.",
        f"- Mixed precision: `{'bf16' if torch.cuda.is_bf16_supported() else 'fp16'}`.",
        f"- Train/validation/holdout jobs: 8/2/4; nhãn dương AI-reviewed trong toàn queue: `{len(found_specs)}`; train labels: {', '.join(train_types)}.",
        f"- Usable chunks: train `{len(examples.get('train', []))}`, validation `{len(examples.get('validation', []))}`, holdout `{len(examples.get('holdout_eval', []))}`.",
        f"- Source sections trong train bị bỏ toàn bộ vì còn candidate không xác minh được span: `{len(excluded_sections)}`; chunks có span mơ hồ: `{skipped_ambiguous}`; span lệch token/quá dài: `{skipped_unaligned}`.",
        f"- AI-review decisions: `{dict(review_counts)}`.",
        "- Negative-type sampling thực nghiệm: `0.00`, `0.50`, `0.75`; mỗi example nhận phần tương ứng của các nhãn train vắng mặt qua `ner_negatives`. Đây là cách vận hành để so sánh các tỷ lệ, không tái tạo nguyên sampler cùng-batch trong paper. Loss-level `negatives=1.0` và `masking=none` được giữ cố định; chúng khác với negative entity-type sampling.",
        "",
        "## Baseline",
        "",
        f"- Validation: {format_metric(baseline['validation'])}",
        f"- Holdout: {format_metric(baseline['holdout_eval'])}",
        "",
        "## Kết quả từng tỷ lệ",
        "",
        "| Negative types | Validation | Holdout |",
        "|---:|---|---|",
    ]
    for result in results:
        report.append(f"| {result['ratio']:.0%} | {format_metric(result['validation'])} | {format_metric(result['holdout'])} |")
    if EXTERNAL_METRICS_PATH.exists():
        external = load_json(EXTERNAL_METRICS_PATH)
        report.extend([
            "",
            "## External English benchmark baseline",
            "",
            "SkillSpan TECH is a separate cross-source/cross-language evaluation set, not the Vietnamese Saramin benchmark. The six project labels are collapsed to one class and scored against SkillSpan Knowledge spans; Skill spans are not treated as negatives.",
            "",
            "| Split | Jobs | Precision | Recall | F1 | TP | FP | FN |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for split_name in ("validation", "holdout"):
            values = external["results"][split_name]
            report.append(
                f"| {split_name} | {values['jobs']} | {values['precision']:.3f} | "
                f"{values['recall']:.3f} | {values['f1']:.3f} | {values['tp']} | "
                f"{values['fp']} | {values['fn']} |"
            )
        report.extend([
            "",
            "The fixed threshold is 0.40. The external holdout has been evaluated once; use validation for subsequent model or threshold selection and retain the holdout for final reporting.",
            "Details and split manifest: `data/skillspan_external/README.md`.",
        ])
    report.extend([
        "",
        f"Fine-tune tốt nhất trên validation: **{best_finetuned_ratio:.0%}**, F1=`{best_finetuned_validation_f1:.3f}`. Holdout chỉ được báo cáo để đối chiếu.",
        ("Baseline tốt hơn fine-tune trên validation; giữ checkpoint gốc làm model được chọn." if baseline_selected
         else f"Fine-tune `{best_ratio:.0%}` vượt baseline validation và được chọn."),
        f"Model được giữ/chọn: `{best_dir.relative_to(ROOT).as_posix()}`.",
        "",
        "## Giới hạn",
        "",
        "1. 14 job là tập quá nhỏ cho kết luận tổng quát; validation chỉ có 2 job.",
        "2. Annotation train do AI rà soát theo rubric, chưa có người xác nhận; một số span dịch nghĩa hoặc thiếu vị trí cụ thể bị loại và section tương ứng không được dùng train.",
        "3. Validation/holdout dùng benchmark `draft_single_annotator`; độ chính xác của metric bị giới hạn bởi chất lượng benchmark.",
        "4. Đây là pilot nhỏ với 20 bước mỗi cấu hình; cần thêm job và lượt review độc lập trước khi chọn checkpoint cho MVP.",
        "",
        "Tham khảo: [GLiNER paper, mục negative entity sampling](https://aclanthology.org/2024.naacl-long.300.pdf); [tài liệu train GLiNER](https://urchade.github.io/GLiNER/training.html).",
        "",
    ])
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print((f"Baseline retained; best fine-tuned ratio was {best_finetuned_ratio:.2f}"
           if baseline_selected else f"Selected fine-tuned ratio by validation: {best_ratio:.2f}")
          + f"; saved model to {best_dir}")
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
