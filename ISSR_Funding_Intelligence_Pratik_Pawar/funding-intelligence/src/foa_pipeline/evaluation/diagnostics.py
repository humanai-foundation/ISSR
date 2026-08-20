"""
Diagnostics for *why* the tagger scores as it does, as opposed to what it scores.

At the current gold-set size (20 FOAs, 81 tags) a global F1 movement of ±0.02 is
roughly one tag decision, so F1 alone cannot tell a real improvement from noise.
Separation can: it asks whether Layer 2 assigns systematically higher cosine
scores to correct concepts than to incorrect ones, across every scored tag
rather than only the ones that crossed a threshold.

This matters because measurement already showed the scores are compressed —
genuine matches sit at cosine 0.35-0.50, the same band as the noise, which is
why every confidence floor tested (0.40-0.55) made F1 worse. A change that
widens separation is working even if F1 moves within noise; a change that
narrows it is harmful even if F1 happens to tick up.

Reads the artefacts written by `evaluation.runner`, so run an evaluation first.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

L2_LAYER = "layer_2_embedding"


def _auc(positives: Sequence[float], negatives: Sequence[float]) -> Optional[float]:
    """
    Probability a random correct tag outscores a random incorrect one.

    This is the Mann-Whitney U statistic (equivalently ROC AUC), computed
    directly rather than via a dependency. 0.5 means the score carries no
    information about correctness; 1.0 means perfect separation.
    """
    if not positives or not negatives:
        return None

    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(round((pct / 100.0) * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def _summarise(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0, "mean": 0.0, "p25": 0.0, "median": 0.0, "p75": 0.0}
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "p25": _percentile(values, 25),
        "median": _percentile(values, 50),
        "p75": _percentile(values, 75),
    }


def _load(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        legacy = path.with_name(path.name.replace("_gold", "").replace("_silver", ""))
        hint = ""
        if legacy.exists():
            hint = (
                f" An un-namespaced {legacy.name} exists from before error logs "
                "were split per eval set; re-run the evaluation to regenerate it."
            )
        raise FileNotFoundError(
            f"{path} not found. Run an evaluation first "
            f"(python -m foa_pipeline.cli evaluate --gold).{hint}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cosine_separation(evaluation_dir: Path, eval_set: str = "gold") -> Dict[str, Any]:
    """
    Compare Layer 2 cosine scores for correct vs incorrect tags.

    Only Layer 2 evidence is considered: Layer 1 always reports confidence 1.0
    and Layer 3 reports a fixed 0.95, so neither carries a score whose
    separation is meaningful.

    `eval_set` selects which run's error logs to read. It defaults to "gold"
    because separation is a reported diagnostic, and the silver set's labels are
    model-generated — measuring separation against them would describe agreement
    with another model rather than with ground truth.
    """
    true_positives = _load(evaluation_dir / f"true_positives_{eval_set}.json")
    false_positives = _load(evaluation_dir / f"false_positives_{eval_set}.json")

    if not any(t.get("layer") for t in true_positives):
        raise ValueError(
            f"true_positives_{eval_set}.json has no 'layer' field. It was produced "
            "by an older runner that did not record evidence for true positives; "
            "re-run the evaluation to regenerate it."
        )

    def l2_scores(rows: List[Dict[str, Any]], category: Optional[str] = None) -> List[float]:
        return [
            float(r.get("confidence", 0.0))
            for r in rows
            if r.get("layer") == L2_LAYER
            and (category is None or r.get("category") == category)
        ]

    report: Dict[str, Any] = {"overall": {}, "per_category": {}}

    tp_all, fp_all = l2_scores(true_positives), l2_scores(false_positives)
    report["overall"] = {
        "correct": _summarise(tp_all),
        "incorrect": _summarise(fp_all),
        "auc": _auc(tp_all, fp_all),
        "mean_gap": (
            (sum(tp_all) / len(tp_all)) - (sum(fp_all) / len(fp_all))
            if tp_all and fp_all
            else None
        ),
    }

    categories = {r.get("category") for r in true_positives + false_positives}
    for category in sorted(c for c in categories if c):
        tp_c, fp_c = l2_scores(true_positives, category), l2_scores(false_positives, category)
        report["per_category"][category] = {
            "correct": _summarise(tp_c),
            "incorrect": _summarise(fp_c),
            "auc": _auc(tp_c, fp_c),
        }

    return report


def format_separation_report(report: Dict[str, Any]) -> str:
    """Render a separation report for the terminal."""
    lines: List[str] = []
    overall = report["overall"]
    correct, incorrect = overall["correct"], overall["incorrect"]

    lines.append("Layer 2 cosine separation (correct vs incorrect tags)")
    lines.append("=" * 66)
    lines.append(f"{'':<12} {'n':>4} {'mean':>7} {'p25':>7} {'median':>7} {'p75':>7}")
    for name, stats in (("correct", correct), ("incorrect", incorrect)):
        lines.append(
            f"{name:<12} {stats['n']:>4} {stats['mean']:>7.3f} {stats['p25']:>7.3f} "
            f"{stats['median']:>7.3f} {stats['p75']:>7.3f}"
        )

    auc = overall["auc"]
    gap = overall["mean_gap"]
    lines.append("")
    if auc is None:
        lines.append("AUC: n/a (need both correct and incorrect Layer 2 tags)")
    else:
        lines.append(f"AUC:      {auc:.3f}   (0.5 = score says nothing about correctness)")
        lines.append(f"mean gap: {gap:+.3f}")

    lines.append("")
    lines.append("Per category:")
    lines.append(f"  {'category':<22} {'AUC':>6} {'correct n':>10} {'incorrect n':>12}")
    for category, stats in report["per_category"].items():
        cat_auc = stats["auc"]
        auc_text = f"{cat_auc:>6.3f}" if cat_auc is not None else f"{'n/a':>6}"
        lines.append(
            f"  {category:<22} {auc_text} {stats['correct']['n']:>10} "
            f"{stats['incorrect']['n']:>12}"
        )

    return "\n".join(lines)
