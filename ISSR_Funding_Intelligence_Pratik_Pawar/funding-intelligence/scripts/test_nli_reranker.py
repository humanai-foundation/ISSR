"""
Experiment: can a zero-shot NLI cross-encoder rerank method/population
candidates better than Layer 2's raw cosine similarity, for free (no
training)?

Method: pull L2's FULL candidate list for method/population on the 20 gold
FOAs (thresholds overridden near-zero so nothing is cut before we see it),
score each (FOA, concept) candidate's context_snippet against a hypothesis
built from the concept label using an off-the-shelf NLI cross-encoder, and
compare two things against gold:

  1. Oracle: best achievable P/R/F1 if concepts were selected purely by NLI
     entailment score at the single best cutoff (same methodology as
     Documentation/EVALUATION.md 4i's oracle analysis).
  2. Drop-in: same selection rule production uses today (top-3 by score per
     category) but with NLI score substituted for cosine score.

Not wired into the pipeline. Reports numbers only; a human decides whether
this is worth implementing for real based on what comes out.
"""

import sys
sys.path.insert(0, "src")

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from foa_pipeline.config import get_config  # noqa: E402
from foa_pipeline.ontology.store import OntologyStore  # noqa: E402
from foa_pipeline.tagging.layer2_embedding import L2Tagger  # noqa: E402
from foa_pipeline.normalisation.boilerplate import strip_boilerplate  # noqa: E402

GOLD_PATH = "data/evaluation/eval_set_gold.json"
TARGET_CATEGORIES = {"method", "population"}

HYPOTHESIS_TEMPLATES = {
    "method": "This grant program requires or uses {label} as a research method.",
    "population": "This grant program targets or serves {label} as a population.",
}


def load_gold():
    return json.loads(Path(GOLD_PATH).read_text())


def main():
    config = get_config()
    store = OntologyStore(config.app_db_path)

    # Near-zero thresholds for the two target categories so tag_text returns
    # every candidate it scored, not just what would survive production's cut.
    thresholds = dict(config.cosine_thresholds)
    for cat in TARGET_CATEGORIES:
        thresholds[cat] = -1.0

    l2 = L2Tagger(model_name=config.embedding_model, thresholds=thresholds,
                  cache_dir=config.embeddings_cache_dir)
    l2.load_model()
    l2.build_embeddings(store)

    print("Loading NLI cross-encoder (cross-encoder/nli-deberta-v3-base)...")
    from sentence_transformers import CrossEncoder
    nli = CrossEncoder("cross-encoder/nli-deberta-v3-base")
    # Label order for this checkpoint: contradiction=0, entailment=1, neutral=2
    label_mapping = nli.config.id2label

    import sqlite3
    con = sqlite3.connect(config.app_db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    gold = load_gold()
    candidates = []  # (foa_id, concept_id, category, label, cosine, nli_entail, is_gold)

    for entry in gold:
        foa_id = entry["foa_id"]
        gold_ids = set(entry["human_tags"])

        cur.execute(
            "SELECT title, program_description, eligibility_description, additional_info "
            "FROM foa_records WHERE foa_id = ?",
            (foa_id,),
        )
        row = cur.fetchone()
        if row is None:
            continue

        head = strip_boilerplate(
            " ".join(p for p in (row["title"], row["program_description"]) if p)
        )
        eligibility_text = strip_boilerplate(row["eligibility_description"] or "")
        tail = strip_boilerplate(row["additional_info"] or "")
        full_text = " ".join(s for s in (head, eligibility_text, tail) if s)
        if not full_text.strip():
            continue

        evidence = l2.tag_text(full_text, title=row["title"], title_weight=0.0)
        cat_evidence = [ev for ev in evidence if ev.category in TARGET_CATEGORIES]
        print(f"{entry['title'][:60]:60s} -> {len(cat_evidence)} raw candidates")

        for ev in cat_evidence:
            template = HYPOTHESIS_TEMPLATES[ev.category]
            hypothesis = template.format(label=ev.label)
            scores = nli.predict([(ev.context_snippet, hypothesis)])[0]
            entail_idx = [k for k, v in label_mapping.items() if v == "entailment"][0]
            entail_score = float(scores[entail_idx])

            candidates.append({
                "foa_id": foa_id,
                "concept_id": ev.concept_id,
                "category": ev.category,
                "label": ev.label,
                "cosine": ev.confidence,
                "nli_entail": entail_score,
                "is_gold": ev.concept_id in gold_ids,
            })

    Path("data/evaluation/nli_reranker_candidates.json").write_text(json.dumps(candidates, indent=2))
    print(f"\nWrote {len(candidates)} scored candidates to data/evaluation/nli_reranker_candidates.json")

    # Also record total gold tag counts per category (for recall denominator)
    gold_counts = {"method": 0, "population": 0}
    for entry in gold:
        for t in entry["human_tags"]:
            if t.startswith("method_"):
                gold_counts["method"] += 1
            elif t.startswith("pop_"):
                gold_counts["population"] += 1
    print("Gold tag counts:", gold_counts)


if __name__ == "__main__":
    main()
