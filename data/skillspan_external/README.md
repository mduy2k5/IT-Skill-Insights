# SkillSpan TECH external validation and holdout

> Separate English, external evaluation set. Do not merge its scores with the 14-job Saramin benchmark.

## Split and annotation

- Upstream revision: `2ccf3de5b5af7a5409b8dd814fb1315dd6e0ae1b`.
- Validation comes only from upstream `dev.json`; holdout comes only from upstream `test.json`.
- Kept only `source=tech` and grouped all sentences by the upstream job ID before assigning each posting to one split.
- Exact normalized-description overlap between validation and holdout: `0`.
- Counts below are measured from the pinned JSON files. The paper's table reports 30 TECH dev jobs and 32 TECH test jobs, while this repository revision contains 29 and 31 respectively; the split manifest records the actual evaluated IDs.
- The SkillSpan paper reports expert span annotations and describes the test split as annotated by three annotators with majority-vote aggregation. The validation split was annotated by one annotator.
- Source BIO anomalies detected: `1`. An orphan `I` is retained as a provisional span marked `needs_review=true`; source tag arrays are preserved. It is not part of the primary Knowledge metric.
- This is not the project's six-label Vietnamese gold. For the project's technical entity extraction, compare the union of its six predicted labels to SkillSpan `Knowledge` spans; keep SkillSpan `Skill` spans available for separate analysis, not as negatives.

## Dataset size

| Split | Jobs | Sentences | Tokens | Skill spans | Knowledge spans |
|---|---:|---:|---:|---:|---:|
| validation | 29 | 2156 | 20901 | 545 | 806 |
| holdout | 31 | 2286 | 20213 | 440 | 806 |

## Use

1. Use validation to compare checkpoints and thresholds.
2. Keep holdout frozen until the model and threshold are selected; report it once for final comparison.
3. Do not use either split for fine-tuning or training negatives.
4. Keep the original internal Saramin split for Vietnamese evaluation. This external English set measures cross-source and cross-language transfer, not MVP performance on Vietnamese postings.

## Provenance and attribution

- Dataset: [SkillSpan repository](https://github.com/kris927b/SkillSpan), converted from the released JSON sentence annotations.
- Paper: Zhang et al. (2022), [SkillSpan: Hard and Soft Skill Extraction from English Job Postings](https://aclanthology.org/2022.naacl-main.366/).
- The paper identifies the TECH source as Stack Overflow job postings licensed under CC BY-SA. Stack Overflow states contributions from 2018-05-02 onward use CC BY-SA 4.0; assigning version 4.0 to this 2020-2021 sample is based on source/date, not post-level license metadata. Retain attribution and ShareAlike terms when redistributing derived text.
- [Stack Overflow licensing information](https://stackoverflow.com/help/licensing).
- The original repository's MIT license covers its software; dataset licensing is source-specific and documented in the paper/data statement.

## Files

- `validation_tech.json`: postings reconstructed from all released sentence rows and exact Skill/Knowledge spans from upstream dev.
- `holdout_tech.json`: postings reconstructed from all released sentence rows and exact Skill/Knowledge spans from upstream test.
- `split_manifest.csv`: one row per posting, with split, annotation counts, and normalized text hash.

## Reproduce

```powershell
git clone --depth 1 https://github.com/kris927b/SkillSpan.git .tmp/skillspan_source
.venv\Scripts\python.exe scripts\prepare_skillspan_external_benchmark.py
.venv\Scripts\python.exe scripts\evaluate_skillspan_external.py --threshold 0.40
```

## Initial GLiNER baseline

- Checkpoint: `urchade/gliner_multi-v2.1`; threshold `0.40`; exact character-span matching.
- This is a fixed-threshold baseline, not a threshold sweep. Holdout has been evaluated once and should remain frozen while selecting later checkpoints on validation.

| Split | Jobs | Precision | Recall | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| validation | 29 | 0.510 | 0.336 | 0.405 | 271 | 260 | 535 |
| holdout | 31 | 0.588 | 0.336 | 0.428 | 271 | 190 | 535 |

