"""
Reports agreement between the human gold labels and the LLM synthetic
cross-check on the same 40 FOAs.

Run only after both exist: eval_set_gold.json has all 40 entries (i.e.
after merge_annotation_packet.py) and gold_expansion_synthetic_crosscheck.json
has all 40.

Reported as "human vs. synthetic diagnostic cross-check" throughout, on
purpose -- see generate_synthetic_crosscheck.py's docstring for why this is
not inter-annotator agreement and must never be written up as if it were.
"""

import json
from collections import defaultdict
from pathlib import Path

GOLD_PATH = "data/evaluation/eval_set_gold.json"
SYNTHETIC_PATH = "data/evaluation/gold_expansion_synthetic_crosscheck.json"


def category_of(concept_id: str) -> str:
    prefix_map = {
        "great_": "sponsor_theme",
        "sdg_": "research_domain",
        "method_": "method",
        "pop_": "population",
        "nsf_": "research_discipline",
    }
    for prefix, cat in prefix_map.items():
        if concept_id.startswith(prefix):
            return cat
    return "unknown"


def main() -> None:
    gold = {e["foa_id"]: set(e["human_tags"]) for e in json.loads(Path(GOLD_PATH).read_text())}
    synthetic = {
        e["foa_id"]: set(e["synthetic_tags"])
        for e in json.loads(Path(SYNTHETIC_PATH).read_text())
    }

    common_ids = set(gold) & set(synthetic)
    if len(common_ids) < len(gold):
        print(
            f"WARNING: only {len(common_ids)}/{len(gold)} gold FOAs have a synthetic "
            "counterpart -- run merge_annotation_packet.py and/or "
            "generate_synthetic_crosscheck.py first."
        )

    global_tp = global_fp = global_fn = 0
    per_cat = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for foa_id in common_ids:
        human_tags = gold[foa_id]
        synth_tags = synthetic[foa_id]

        tp = human_tags & synth_tags
        fp = synth_tags - human_tags  # synthetic said yes, human said no
        fn = human_tags - synth_tags  # human said yes, synthetic said no

        global_tp += len(tp)
        global_fp += len(fp)
        global_fn += len(fn)

        for t in tp:
            per_cat[category_of(t)]["tp"] += 1
        for t in fp:
            per_cat[category_of(t)]["fp"] += 1
        for t in fn:
            per_cat[category_of(t)]["fn"] += 1

    def prf(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        return p, r, f1

    print(f"=== Human vs. Synthetic diagnostic cross-check ({len(common_ids)} FOAs) ===")
    print("NOT inter-annotator agreement -- treating human labels as reference,")
    print("synthetic (LLM) labels as the thing being scored against them.\n")

    p, r, f1 = prf(global_tp, global_fp, global_fn)
    print(f"Global: P={p:.3f} R={r:.3f} F1={f1:.3f}  (TP={global_tp} FP={global_fp} FN={global_fn})\n")

    print("Per category:")
    for cat, counts in sorted(per_cat.items()):
        p, r, f1 = prf(counts["tp"], counts["fp"], counts["fn"])
        print(f"  {cat:20s} P={p:.3f} R={r:.3f} F1={f1:.3f} "
              f"(TP={counts['tp']} FP={counts['fp']} FN={counts['fn']})")


if __name__ == "__main__":
    main()
