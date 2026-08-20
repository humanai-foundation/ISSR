"""
Discipline classification benchmark against the NSF award corpus.

This measures something the gold set cannot. `research_discipline` has eight
concepts and the gold set carries 23 discipline tags across 20 FOAs — roughly
three examples per directorate, where a single annotation disagreement swings
per-concept F1 by tens of points. Any conclusion drawn at that scale is noise.
The NSF award corpus supplies hundreds of documents whose directorate was
assigned by NSF itself, which buys the resolution to say which directorates the
encoder actually confuses.

It is a *ranking* benchmark, not a thresholded one. Production tagging asks
"did this concept clear its threshold"; here every award has exactly one correct
directorate, so the informative question is "is the right one ranked first".
That also makes the numbers directly comparable to published work: OpenAlex's
production classifier reports top-1 0.53 / top-3 0.73 over a much larger label
space, which is the reference point this project should be judged against.

Two accuracies are reported, and both matter:
  - **strict**  — the prediction must equal the managing directorate.
  - **lenient** — any co-funding directorate counts. Roughly one award in seven
    is co-funded, and calling a prediction of the co-funder "wrong" penalises
    the tagger for being right about genuinely interdisciplinary work.

The distribution shift is real and must be quoted alongside any number from
here: awards describe funded projects in the past tense, FOAs solicit them.
This complements the gold set; it does not replace it.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DISCIPLINE_CATEGORY = "research_discipline"
CORPUS_FILENAME = "nsf_awards.jsonl"

SPLITS = ("tune", "eval", "all")


def assign_split(award_id: str) -> str:
    """
    Deterministically place an award in the tuning or held-out half.

    Hashing the award ID rather than shuffling means the split is stable across
    runs, machines and re-harvests: an award that was held out stays held out
    even after the corpus grows. That is what makes a before/after comparison on
    the eval half meaningful rather than a reshuffle of which documents are easy.
    """
    digest = hashlib.sha256(award_id.encode("utf-8")).hexdigest()
    return "tune" if int(digest[:8], 16) % 2 == 0 else "eval"


def load_award_corpus(
    evaluation_dir: Path,
    limit: Optional[int] = None,
    split: str = "all",
) -> List[Dict[str, Any]]:
    """
    Read the harvested award corpus, skipping malformed lines.

    `split` selects half the corpus. Concept descriptions are edited by hand in
    response to what the benchmark reports, which is tuning — so the numbers
    quoted as results must come from awards that played no part in those edits.
    Use "tune" while iterating and "eval" when reporting.
    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")

    path = evaluation_dir / CORPUS_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"No award corpus at {path}. Run `cli harvest-nsf-awards` first."
        )

    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not (record.get("abstract") and record.get("primary_concept_id")):
                continue
            if split != "all" and assign_split(str(record.get("award_id", ""))) != split:
                continue
            records.append(record)
            if limit and len(records) >= limit:
                break
    return records


def rank_concepts(scores: Dict[str, float]) -> List[str]:
    """
    Concept IDs ordered by descending score.

    Ties break on concept ID rather than dict order so a run is reproducible;
    an arbitrary tiebreak would make top-1 accuracy depend on insertion order.
    """
    return [cid for cid, _score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_predictions(
    records: Sequence[Dict[str, Any]],
    rankings: Sequence[Sequence[str]],
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Score precomputed rankings against the corpus labels.

    Separated from the tagging step so the metric logic is testable without
    loading a 400MB sentence-transformer.
    """
    if len(records) != len(rankings):
        raise ValueError("records and rankings must be the same length")

    total = 0
    strict_top1 = 0
    lenient_top1 = 0
    strict_topk = 0
    lenient_topk = 0
    reciprocal_ranks: List[float] = []

    # per-concept: [support, correctly recalled, times predicted, correct when predicted]
    per_concept: Dict[str, List[int]] = {}
    confusion: Dict[Tuple[str, str], int] = {}
    unranked = 0

    for record, ranking in zip(records, rankings):
        primary = record["primary_concept_id"]
        acceptable = set(record.get("acceptable_concept_ids") or [primary])

        if not ranking:
            # No score at all — usually an empty or unembeddable abstract.
            # Counted, never silently dropped, because dropping failures
            # inflates accuracy.
            unranked += 1
            continue

        total += 1
        predicted = ranking[0]
        top_k_set = set(ranking[:top_k])

        stats = per_concept.setdefault(primary, [0, 0, 0, 0])
        stats[0] += 1
        pred_stats = per_concept.setdefault(predicted, [0, 0, 0, 0])
        pred_stats[2] += 1

        if predicted == primary:
            strict_top1 += 1
            stats[1] += 1
            pred_stats[3] += 1
        if predicted in acceptable:
            lenient_top1 += 1
        if primary in top_k_set:
            strict_topk += 1
        if top_k_set & acceptable:
            lenient_topk += 1

        confusion[(primary, predicted)] = confusion.get((primary, predicted), 0) + 1

        rank = ranking.index(primary) + 1 if primary in ranking else 0
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

    concept_metrics: Dict[str, Dict[str, float]] = {}
    for concept_id, (support, recalled, predicted_n, correct_n) in per_concept.items():
        recall = _safe_div(recalled, support)
        precision = _safe_div(correct_n, predicted_n)
        concept_metrics[concept_id] = {
            "support": support,
            "predicted": predicted_n,
            "precision": precision,
            "recall": recall,
            "f1": _safe_div(2 * precision * recall, precision + recall),
        }

    # Macro average is reported because the corpus is not balanced — NSF funds
    # MPS and BIO far more heavily than TIP, so a micro average would mostly
    # describe the two largest directorates.
    scored = [m for m in concept_metrics.values() if m["support"]]
    macro_f1 = _safe_div(sum(m["f1"] for m in scored), len(scored))

    return {
        "total": total,
        "unranked": unranked,
        "top_k": top_k,
        "strict_top1_accuracy": _safe_div(strict_top1, total),
        "lenient_top1_accuracy": _safe_div(lenient_top1, total),
        "strict_topk_accuracy": _safe_div(strict_topk, total),
        "lenient_topk_accuracy": _safe_div(lenient_topk, total),
        "mrr": _safe_div(sum(reciprocal_ranks), len(reciprocal_ranks)),
        "macro_f1": macro_f1,
        "per_concept": concept_metrics,
        "confusion": {f"{t}->{p}": n for (t, p), n in confusion.items()},
    }


def run_discipline_benchmark(
    config: Any,
    store: Any,
    limit: Optional[int] = None,
    top_k: int = 3,
    split: str = "all",
) -> Dict[str, Any]:
    """
    Tag the award corpus with Layer 2 and score the resulting rankings.

    Only Layer 2 participates. Layer 1 is exact-string matching, which on award
    text mostly fires on directorate names quoted inside the abstract — that
    would measure whether NSF names itself, not whether the encoder understands
    the science.
    """
    from ..tagging.layer2_embedding import L2Tagger

    records = load_award_corpus(config.evaluation_dir, limit=limit, split=split)
    if not records:
        raise ValueError(f"Award corpus is empty for split={split!r}")

    tagger = L2Tagger(
        model_name=config.embedding_model,
        thresholds=config.cosine_thresholds,
        cache_dir=config.embeddings_cache_dir,
    )
    tagger.build_embeddings(store)

    rankings: List[List[str]] = []
    for index, record in enumerate(records, start=1):
        # Title and abstract are joined the way the production pipeline joins
        # title and description, so chunking behaves identically.
        text = " ".join(p for p in (record.get("title", ""), record["abstract"]) if p)
        scores = tagger.score_concepts(text, category=DISCIPLINE_CATEGORY)
        rankings.append(rank_concepts(scores))
        if index % 100 == 0:
            logger.info("Scored %s/%s awards", index, len(records))

    report = evaluate_predictions(records, rankings, top_k=top_k)
    report["corpus_size"] = len(records)
    report["split"] = split
    return report


def format_benchmark_report(report: Dict[str, Any], store: Any = None) -> str:
    """Render the benchmark as a fixed-width text report."""

    def label(concept_id: str) -> str:
        if store is None:
            return concept_id
        concept = store.get_concept_by_id(concept_id)
        return concept.label if concept else concept_id

    top_k = report["top_k"]
    split = report.get("split", "all")
    lines = [
        "NSF Award Discipline Benchmark",
        "=" * 62,
        f"Split             : {split}"
        + ("  (tuning half — not a reportable result)" if split == "tune" else ""),
        f"Awards scored     : {report['total']}",
    ]
    if report["unranked"]:
        lines.append(f"Unranked (skipped): {report['unranked']}")
    lines += [
        "",
        f"Top-1 accuracy (strict) : {report['strict_top1_accuracy']:.3f}",
        f"Top-1 accuracy (lenient): {report['lenient_top1_accuracy']:.3f}",
        f"Top-{top_k} accuracy (strict) : {report['strict_topk_accuracy']:.3f}",
        f"Top-{top_k} accuracy (lenient): {report['lenient_topk_accuracy']:.3f}",
        f"Mean reciprocal rank    : {report['mrr']:.3f}",
        f"Macro F1                : {report['macro_f1']:.3f}",
        "",
        "Per directorate:",
        f"  {'concept':<34} {'n':>4} {'P':>6} {'R':>6} {'F1':>6}",
    ]

    for concept_id, metrics in sorted(
        report["per_concept"].items(), key=lambda kv: -kv[1]["support"]
    ):
        lines.append(
            f"  {label(concept_id)[:34]:<34} {int(metrics['support']):>4} "
            f"{metrics['precision']:>6.3f} {metrics['recall']:>6.3f} {metrics['f1']:>6.3f}"
        )

    confusions = sorted(
        ((k, v) for k, v in report["confusion"].items() if k.split("->")[0] != k.split("->")[1]),
        key=lambda kv: -kv[1],
    )
    if confusions:
        lines += ["", "Most frequent confusions (true -> predicted):"]
        for pair, count in confusions[:10]:
            true_id, pred_id = pair.split("->")
            lines.append(f"  {count:>4}  {label(true_id)[:26]:<26} -> {label(pred_id)[:26]}")

    lines += [
        "",
        "Awards are not FOAs: they describe funded work rather than solicit it.",
        "Treat these numbers as a complementary benchmark, not a gold-set result.",
    ]
    return "\n".join(lines)
