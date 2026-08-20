"""Tagging evaluation: metrics, gold/silver comparison, and label generation.

`runner` drives an end-to-end evaluation against an eval set and writes the
error-analysis artefacts; `metrics` holds the reusable scoring helpers.
"""

from .diagnostics import cosine_separation, format_separation_report
from .discipline_benchmark import (
    evaluate_predictions,
    format_benchmark_report,
    load_award_corpus,
    rank_concepts,
    run_discipline_benchmark,
)
from .metrics import compute_metrics, format_eval_report, load_evaluation_set
from .runner import calculate_metrics, run_evaluation

__all__ = [
    "run_evaluation",
    "calculate_metrics",
    "compute_metrics",
    "load_evaluation_set",
    "format_eval_report",
    "cosine_separation",
    "format_separation_report",
    "run_discipline_benchmark",
    "format_benchmark_report",
    "evaluate_predictions",
    "load_award_corpus",
    "rank_concepts",
]
