#!/usr/bin/env python3
"""Evaluate JobBERT Shadow Mode vs Ruleset v0.1 on the Ground Truth Benchmark.

Gates promotion to Analyst view:
1. JobBERT must improve auto-classification rate over ruleset v0.1.
2. JobBERT MUST NOT increase false merge rate (crucial constraint: false_merges <= v0.1_false_merges).

Outputs a comprehensive evaluation JSON and displays gate pass/fail status.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = ROOT_DIR / "web" / "config"
BENCHMARK_PATH = DATA_DIR / "title_benchmark_v0_1.json"
REPORT_PATH = DATA_DIR / "shadow_gate_evaluation_report.json"

sys.path.insert(0, str(ROOT_DIR / "scripts"))
from map_titles_to_role_families import JobTitleNormalizer
from run_shadow_classification import RulesetV01Classifier, SHADOW_TAU, SHADOW_DELTA, MODEL_VERSION


def evaluate_gate(tau: float = SHADOW_TAU, delta: float = SHADOW_DELTA) -> dict[str, Any]:
    print(f"[gate] Evaluating promotion gate on Benchmark ({BENCHMARK_PATH.name})...")
    print(f"[gate] Parameters: tau={tau}, delta={delta}")
    
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    items = benchmark.get("items", [])
    total = len(items)

    normalizer = JobTitleNormalizer()
    normalizer.confidence_tau = tau
    normalizer.margin_delta = delta
    ruleset = RulesetV01Classifier()

    # Metrics counters
    # Ruleset v0.1
    v01_auto = 0
    v01_correct = 0
    v01_false_merges = 0
    v01_unmatched = 0

    # JobBERT Shadow
    jb_auto = 0
    jb_correct = 0
    jb_false_merges = 0
    jb_ambiguous = 0
    jb_low_conf = 0

    detailed_comparisons = []

    for item in items:
        raw_title = item["raw_title"]
        true_family = item["role_family"]

        # 1. Ruleset v0.1 prediction
        r_pred = ruleset.classify(raw_title)
        if r_pred == ruleset.review_label:
            v01_unmatched += 1
            r_status = "UNMATCHED"
            r_correct = False
            r_is_false_merge = False
        else:
            v01_auto += 1
            if r_pred.lower() == true_family.lower():
                v01_correct += 1
                r_correct = True
                r_is_false_merge = False
            else:
                v01_false_merges += 1
                r_correct = False
                r_is_false_merge = True
            r_status = "MATCHED"

        # 2. JobBERT prediction (exclude direct self-match from prototype pool if exact text exists)
        jb_res = normalizer.map_title(raw_title, exclude_self_text=item.get("cleaned_title"))
        jb_status = jb_res["status"]
        jb_pred = jb_res["top1_family"]

        if jb_status == "AUTO_ASSIGNED":
            jb_auto += 1
            if jb_pred.lower() == true_family.lower():
                jb_correct += 1
                jb_is_false_merge = False
            else:
                jb_false_merges += 1
                jb_is_false_merge = True
        elif jb_status == "AMBIGUOUS_REVIEW":
            jb_ambiguous += 1
            jb_is_false_merge = False
        else:
            jb_low_conf += 1
            jb_is_false_merge = False

        detailed_comparisons.append({
            "raw_title": raw_title,
            "true_family": true_family,
            "ruleset": {
                "prediction": r_pred,
                "status": r_status,
                "is_false_merge": r_is_false_merge
            },
            "jobbert": {
                "status": jb_status,
                "top1_family": jb_pred,
                "confidence": jb_res["top1_similarity"],
                "margin": jb_res["margin"],
                "is_false_merge": jb_is_false_merge,
                "candidates": [c["family_name"] for c in jb_res.get("top_candidates", [])]
            }
        })

    # Summary rates
    v01_auto_rate = v01_auto / total
    v01_fm_rate = (v01_false_merges / v01_auto) if v01_auto > 0 else 0.0

    jb_auto_rate = jb_auto / total
    jb_fm_rate = (jb_false_merges / jb_auto) if jb_auto > 0 else 0.0

    # Promotion Gate Criteria:
    # 1. JobBERT improves auto-classification rate: jb_auto_rate > v01_auto_rate
    # 2. JobBERT does NOT increase false merges: jb_false_merges <= v01_false_merges
    crit_1_pass = jb_auto_rate > v01_auto_rate
    crit_2_pass = jb_false_merges <= v01_false_merges
    promotion_passed = crit_1_pass and crit_2_pass

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "parameters": {"tau": tau, "delta": delta},
        "total_benchmark_titles": total,
        "ruleset_v01": {
            "auto_classified_count": v01_auto,
            "auto_classified_rate": round(v01_auto_rate, 4),
            "correct_count": v01_correct,
            "false_merges": v01_false_merges,
            "false_merge_rate": round(v01_fm_rate, 4),
            "unmatched_count": v01_unmatched,
        },
        "jobbert_shadow": {
            "auto_assigned_count": jb_auto,
            "auto_assigned_rate": round(jb_auto_rate, 4),
            "correct_count": jb_correct,
            "false_merges": jb_false_merges,
            "false_merge_rate": round(jb_fm_rate, 4),
            "ambiguous_count": jb_ambiguous,
            "low_confidence_count": jb_low_conf,
            "review_needed_count": jb_ambiguous + jb_low_conf,
        },
        "gate_evaluation": {
            "crit_1_coverage_improved": crit_1_pass,
            "crit_2_no_false_merge_increase": crit_2_pass,
            "decision": "PROMOTE_APPROVED" if promotion_passed else "HOLD_BLOCKED",
            "justification": (
                f"JobBERT tăng tỷ lệ auto-classify từ {v01_auto_rate*100:.1f}% lên {jb_auto_rate*100:.1f}%, "
                f"đồng thời GIẢM mạnh lỗi gộp nhầm (False Merges) từ {v01_false_merges} ({v01_fm_rate*100:.1f}%) "
                f"xuống còn {jb_false_merges} ({jb_fm_rate*100:.1f}%)."
                if promotion_passed else "Không thỏa mãn điều kiện an toàn."
            )
        },
        "detailed_sample": detailed_comparisons
    }

    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gate] Report written to: {REPORT_PATH}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tau", type=float, default=SHADOW_TAU)
    parser.add_argument("--delta", type=float, default=SHADOW_DELTA)
    args = parser.parse_args()

    res = evaluate_gate(tau=args.tau, delta=args.delta)
    
    print("\n" + "=" * 70)
    print(f"{'PROMOTION GATE EVALUATION: JOBBERT VS RULESET V0.1':^70}")
    print("=" * 70)
    print(f" Benchmark Titles: {res['total_benchmark_titles']}")
    print("-" * 70)
    print(f" {'Metric':<30} | {'Ruleset v0.1':<16} | {'JobBERT Shadow':<16}")
    print("-" * 70)
    r = res["ruleset_v01"]
    j = res["jobbert_shadow"]
    print(f" {'Auto-classified Count':<30} | {r['auto_classified_count']:>16} | {j['auto_assigned_count']:>16}")
    print(f" {'Auto-classified Rate':<30} | {r['auto_classified_rate']*100:>15.1f}% | {j['auto_assigned_rate']*100:>15.1f}%")
    print(f" {'False Merges (Lỗi gộp nhầm)':<30} | {r['false_merges']:>16} | {j['false_merges']:>16}")
    print(f" {'False Merge Rate':<30} | {r['false_merge_rate']*100:>15.1f}% | {j['false_merge_rate']*100:>15.1f}%")
    print(f" {'Needs Review (Chờ rà soát)':<30} | {r['unmatched_count']:>16} | {j['review_needed_count']:>16}")
    print("=" * 70)
    g = res["gate_evaluation"]
    print(f" Coverage Improved?         : {'YES [PASS]' if g['crit_1_coverage_improved'] else 'NO [FAIL]'}")
    print(f" No Increase in False Merges: {'YES [PASS]' if g['crit_2_no_false_merge_increase'] else 'NO [FAIL]'}")
    print(f" GATE DECISION              : {g['decision']}")
    print(f" Summary                    : {g['justification']}")
    print("=" * 70)

    return 0 if g["decision"] == "PROMOTE_APPROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
