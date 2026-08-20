"""
Evaluate the Tagging Pipeline against gold standard or synthetic eval sets.

Usage:
  PYTHONPATH=src python src/foa_pipeline/evaluate.py --gold    # Use hand-curated gold standard
  PYTHONPATH=src python src/foa_pipeline/evaluate.py            # Use synthetic eval set
"""

import argparse
import json
import logging
from collections import defaultdict

from foa_pipeline.config import get_config
from foa_pipeline.ontology.store import OntologyStore
from foa_pipeline.storage.database import Database
from foa_pipeline.tagging.pipeline import TaggerPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def calculate_metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def eval_set_slug(use_gold: bool) -> str:
    """
    Short name for the eval set, used to namespace this run's output files.

    Both modes previously wrote to the same paths, so a silver run silently
    replaced the gold error logs that Documentation/EVALUATION.md 5 presents as the reported
    error analysis — the files kept their names while describing a different
    set of FOAs. Namespacing makes the two runs coexist.
    """
    return "gold" if use_gold else "silver"


def run_evaluation(use_gold=False, use_db_tags=False):
    config = get_config()
    store = OntologyStore(config.app_db_path)
    db = Database(config.app_db_path)

    # Select eval file
    if use_gold:
        eval_file = config.evaluation_dir / "eval_set_gold.json"
    else:
        eval_file = config.evaluation_dir / "eval_set_50.json"

    if not eval_file.exists():
        logging.error(f"{eval_file} not found.")
        return

    with open(eval_file) as f:
        foas = json.load(f)

    # If using gold standard, we evaluate from DB tags directly
    # (no need to re-run the tagger)
    tagger = None
    if not use_db_tags and not use_gold:
        tagger = TaggerPipeline(config, store)
        tagger.initialize()

    global_tp = 0
    global_fp = 0
    global_fn = 0

    cat_tp = defaultdict(int)
    cat_fp = defaultdict(int)
    cat_fn = defaultdict(int)

    false_positives_log = []
    false_negatives_log = []
    true_positives_log = []
    per_foa_results = []

    logging.info("Evaluating %d FOAs from %s...", len(foas), eval_file.name)

    for foa in foas:
        human_tags = set(foa.get("human_tags", []))
        if not human_tags:
            continue

        # Validate human tags against ontology
        valid_human = set()
        for t in human_tags:
            c = store.get_concept_by_id(t)
            if c:
                valid_human.add(t)
            else:
                logging.warning("Invalid concept ID in gold standard: %s", t)

        if not valid_human:
            continue

        # Get predicted tags
        if use_gold or use_db_tags:
            # Use tags already in the database
            db_tags = db.get_tags_for_foa(foa["foa_id"])
            predicted_tags = set(t["ontology_concept_id"] for t in db_tags)
            predicted_tags_raw = db_tags
        else:
            predicted_tags_raw = tagger.tag_record(foa)
            predicted_tags = set(t["ontology_concept_id"] for t in predicted_tags_raw)

        # Calculate intersections
        tp_set = valid_human.intersection(predicted_tags)
        fp_set = predicted_tags - valid_human
        fn_set = valid_human - predicted_tags

        global_tp += len(tp_set)
        global_fp += len(fp_set)
        global_fn += len(fn_set)

        # Per-FOA result for the report
        per_foa_results.append({
            "foa_id": foa["foa_id"],
            "title": foa.get("title", ""),
            "human_tags": list(valid_human),
            "predicted_tags": list(predicted_tags),
            "tp": list(tp_set),
            "fp": list(fp_set),
            "fn": list(fn_set),
        })

        for t in tp_set:
            concept = store.get_concept_by_id(t)
            if concept:
                cat_tp[concept.category] += 1
                # Layer and confidence are recorded for true positives as well as
                # false positives so the two are directly comparable. Without the
                # TP side, there is no way to measure how well Layer 2 separates
                # correct from incorrect matches — which is the diagnostic that
                # matters when cosine scores are compressed.
                evidence = next(
                    (p for p in predicted_tags_raw if p.get("ontology_concept_id") == t),
                    None,
                )
                true_positives_log.append({
                    "foa_id": foa["foa_id"],
                    "title": foa.get("title", ""),
                    "concept": t,
                    "label": concept.label,
                    "category": concept.category,
                    "layer": evidence.get("source_layer", "unknown") if evidence else "unknown",
                    "confidence": evidence.get("confidence", 0) if evidence else 0,
                    "context": (evidence.get("context_snippet", "") if evidence else "")[:200],
                })

        for t in fp_set:
            concept = store.get_concept_by_id(t)
            if concept:
                cat_fp[concept.category] += 1
                evidence = next(
                    (p for p in predicted_tags_raw if p.get("ontology_concept_id") == t),
                    None,
                )
                false_positives_log.append({
                    "foa_id": foa["foa_id"],
                    "title": foa.get("title", ""),
                    "concept": t,
                    "label": concept.label,
                    "category": concept.category,
                    "layer": evidence.get("source_layer", "unknown") if evidence else "unknown",
                    "confidence": evidence.get("confidence", 0) if evidence else 0,
                    "context": (evidence.get("context_snippet", "") if evidence else "")[:200],
                })

        for t in fn_set:
            concept = store.get_concept_by_id(t)
            if concept:
                cat_fn[concept.category] += 1
                false_negatives_log.append({
                    "foa_id": foa["foa_id"],
                    "title": foa.get("title", ""),
                    "concept": t,
                    "label": concept.label,
                    "category": concept.category,
                })

    # Print metrics
    p, r, f1 = calculate_metrics(global_tp, global_fp, global_fn)
    logging.info("=" * 60)
    logging.info("GLOBAL METRICS")
    logging.info("=" * 60)
    logging.info("Precision: %.3f | Recall: %.3f | F1: %.3f", p, r, f1)
    logging.info("TP: %d, FP: %d, FN: %d", global_tp, global_fp, global_fn)

    logging.info("")
    logging.info("PER-CATEGORY METRICS")
    logging.info("-" * 60)
    all_cats = sorted(set(list(cat_tp.keys()) + list(cat_fp.keys()) + list(cat_fn.keys())))
    for cat in all_cats:
        cp, cr, cf1 = calculate_metrics(cat_tp[cat], cat_fp[cat], cat_fn[cat])
        logging.info(
            "%-20s P=%.3f  R=%.3f  F1=%.3f  (TP=%d, FP=%d, FN=%d)",
            cat.upper(), cp, cr, cf1, cat_tp[cat], cat_fp[cat], cat_fn[cat]
        )

    # Dump error logs, namespaced by eval set so a silver run cannot overwrite
    # the gold analysis (or vice versa).
    out_dir = config.evaluation_dir
    slug = eval_set_slug(use_gold)
    with open(out_dir / f"false_positives_{slug}.json", "w") as f:
        json.dump(false_positives_log, f, indent=2)
    with open(out_dir / f"false_negatives_{slug}.json", "w") as f:
        json.dump(false_negatives_log, f, indent=2)
    with open(out_dir / f"true_positives_{slug}.json", "w") as f:
        json.dump(true_positives_log, f, indent=2)
    with open(out_dir / f"per_foa_results_{slug}.json", "w") as f:
        json.dump(per_foa_results, f, indent=2)

    # Summary JSON for the report
    summary = {
        "eval_set": eval_file.name,
        "total_foas_evaluated": len([f for f in foas if f.get("human_tags")]),
        "global": {
            "precision": round(p, 3),
            "recall": round(r, 3),
            "f1": round(f1, 3),
            "tp": global_tp,
            "fp": global_fp,
            "fn": global_fn,
        },
        "per_category": {},
    }
    for cat in all_cats:
        cp, cr, cf1 = calculate_metrics(cat_tp[cat], cat_fp[cat], cat_fn[cat])
        summary["per_category"][cat] = {
            "precision": round(cp, 3), "recall": round(cr, 3), "f1": round(cf1, 3),
            "tp": cat_tp[cat], "fp": cat_fp[cat], "fn": cat_fn[cat],
        }
    with open(out_dir / f"evaluation_summary_{slug}.json", "w") as f:
        json.dump(summary, f, indent=2)

    logging.info("")
    logging.info("Saved error analysis to %s", out_dir)
    logging.info("  - false_positives_%s.json (%d entries)", slug, len(false_positives_log))
    logging.info("  - false_negatives_%s.json (%d entries)", slug, len(false_negatives_log))
    logging.info("  - true_positives_%s.json (%d entries)", slug, len(true_positives_log))
    logging.info("  - per_foa_results_%s.json (%d entries)", slug, len(per_foa_results))
    logging.info("  - evaluation_summary_%s.json", slug)
    if slug != "gold":
        logging.info(
            "These are SILVER-set results (LLM-generated labels) for tuning only; "
            "reported metrics come from --gold."
        )

    store.close()
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the tagging pipeline")
    parser.add_argument("--gold", action="store_true", help="Use hand-curated gold standard")
    args = parser.parse_args()
    run_evaluation(use_gold=args.gold, use_db_tags=args.gold)
