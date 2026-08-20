"""
Evaluation metrics computation.

Computes Precision, Recall, and F1 per ontology category
on the hand-labelled evaluation set.

Each error is traceable to a specific context_snippet via the
provenance metadata, enabling actionable error analysis.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


def compute_metrics(
    predictions: Dict[str, Set[str]],   # foa_id → set of predicted concept_ids
    ground_truth: Dict[str, Set[str]],   # foa_id → set of true concept_ids
    concept_categories: Dict[str, str],  # concept_id → category
) -> Dict[str, Dict[str, Any]]:
    """
    Compute per-category Precision, Recall, F1.

    Returns:
    {
        "overall": {"precision": 0.85, "recall": 0.78, "f1": 0.81, ...},
        "research_domain": {"precision": ..., "recall": ..., "f1": ...},
        "method": {...},
        "population": {...},
        "sponsor_theme": {...}
    }
    """
    category_tp: Dict[str, int] = defaultdict(int)
    category_fp: Dict[str, int] = defaultdict(int)
    category_fn: Dict[str, int] = defaultdict(int)

    for foa_id in ground_truth:
        true_set = ground_truth[foa_id]
        pred_set = predictions.get(foa_id, set())

        for concept_id in pred_set:
            cat = concept_categories.get(concept_id, "unknown")
            if concept_id in true_set:
                category_tp[cat] += 1
            else:
                category_fp[cat] += 1

        for concept_id in true_set:
            if concept_id not in pred_set:
                cat = concept_categories.get(concept_id, "unknown")
                category_fn[cat] += 1

    results: Dict[str, Dict[str, Any]] = {}
    all_tp = sum(category_tp.values())
    all_fp = sum(category_fp.values())
    all_fn = sum(category_fn.values())

    results["overall"] = _prf(all_tp, all_fp, all_fn)

    all_categories = set(
        list(category_tp.keys())
        + list(category_fp.keys())
        + list(category_fn.keys())
    )
    for cat in sorted(all_categories):
        if cat != "unknown":
            results[cat] = _prf(
                category_tp[cat], category_fp[cat], category_fn[cat]
            )

    return results


def _prf(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    """Compute precision, recall, F1 from counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def load_evaluation_set(path: Path) -> Dict[str, Set[str]]:
    """
    Load a hand-labelled evaluation set from JSON.

    Expected format:
    [
        {
            "foa_id": "...",
            "ground_truth_tags": ["concept_id_1", "concept_id_2", ...]
        },
        ...
    ]
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    ground_truth: Dict[str, Set[str]] = {}
    for entry in data:
        foa_id = entry["foa_id"]
        tags = set(entry.get("ground_truth_tags", []))
        ground_truth[foa_id] = tags

    return ground_truth


def save_eval_results(results: Dict[str, Dict[str, Any]], path: Path) -> None:
    """Save evaluation results to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Evaluation results saved to %s", path)


def format_eval_report(results: Dict[str, Dict[str, Any]]) -> str:
    """Format evaluation results as a human-readable markdown table."""
    lines = [
        "# Evaluation Results",
        "",
        "| Category | Precision | Recall | F1 | TP | FP | FN |",
        "|----------|-----------|--------|----|----|----|----|",
    ]

    for category, metrics in results.items():
        lines.append(
            f"| {category} | {metrics['precision']:.4f} | "
            f"{metrics['recall']:.4f} | {metrics['f1']:.4f} | "
            f"{metrics['tp']} | {metrics['fp']} | {metrics['fn']} |"
        )

    return "\n".join(lines)
