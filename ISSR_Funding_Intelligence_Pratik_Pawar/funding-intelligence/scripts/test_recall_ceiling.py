"""
Experiment: of the 28 gold tags currently missed entirely (false negatives),
how many would ever appear as an L2 candidate at ANY threshold, and at what
score? This is the standalone question behind "loosen the threshold" --
answerable without a reranker, and tells us whether that's worth pursuing at
all before building one.

For each FN: is the concept present anywhere in L2's full (unthresholded)
scored output for that FOA? If yes, at what cosine score -- i.e. how loose
would the threshold need to go to catch it, and is that reachable without a
threshold so low it would flood everything else with noise. If no, no
threshold recovers it -- that's a genuine "not in the embedding space near
this text at all" case, not a threshold problem.
"""

import json
import sys
sys.path.insert(0, "src")

from foa_pipeline.config import get_config  # noqa: E402
from foa_pipeline.ontology.store import OntologyStore  # noqa: E402
from foa_pipeline.tagging.layer2_embedding import L2Tagger  # noqa: E402
from foa_pipeline.normalisation.boilerplate import strip_boilerplate  # noqa: E402
import sqlite3  # noqa: E402

FN_PATH = "data/evaluation/false_negatives_gold.json"


def main():
    config = get_config()
    store = OntologyStore(config.app_db_path)
    thresholds = {"default": -1.0}  # unthresholded: every concept scored, no cut
    l2 = L2Tagger(model_name=config.embedding_model, thresholds=thresholds,
                  cache_dir=config.embeddings_cache_dir)
    l2.load_model()
    l2.build_embeddings(store)

    con = sqlite3.connect(config.app_db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    fns = json.loads(open(FN_PATH).read())
    real_thresholds = config.cosine_thresholds

    results = []
    text_cache = {}
    for fn in fns:
        foa_id = fn["foa_id"]
        if foa_id not in text_cache:
            cur.execute(
                "SELECT title, program_description, eligibility_description, additional_info "
                "FROM foa_records WHERE foa_id = ?", (foa_id,),
            )
            row = cur.fetchone()
            head = strip_boilerplate(" ".join(p for p in (row["title"], row["program_description"]) if p))
            elig = strip_boilerplate(row["eligibility_description"] or "")
            tail = strip_boilerplate(row["additional_info"] or "")
            full_text = " ".join(s for s in (head, elig, tail) if s)
            evidence = l2.tag_text(full_text, title=row["title"], title_weight=0.0)
            text_cache[foa_id] = {ev.concept_id: ev.confidence for ev in evidence}

        score = text_cache[foa_id].get(fn["concept"])
        real_threshold = real_thresholds.get(fn["concept"], real_thresholds.get(fn["category"], real_thresholds["default"]))
        results.append({
            "foa_id": foa_id, "title": fn["title"], "concept": fn["concept"],
            "category": fn["category"], "l2_score": score, "real_threshold": real_threshold,
            "recoverable": score is not None,
        })

    recoverable = [r for r in results if r["recoverable"]]
    unrecoverable = [r for r in results if not r["recoverable"]]

    print(f"Total FNs: {len(results)}")
    print(f"Recoverable at SOME threshold (L2 scores it >0 at all): {len(recoverable)}")
    print(f"Never scored by L2 at all (not a threshold problem): {len(unrecoverable)}\n")

    print("Recoverable, sorted by how far below the real threshold they sit:")
    for r in sorted(recoverable, key=lambda x: x["real_threshold"] - x["l2_score"]):
        gap = r["real_threshold"] - r["l2_score"]
        print(f"  [{r['category']:20s}] {r['concept']:12s} score={r['l2_score']:.3f} "
              f"threshold={r['real_threshold']:.2f} gap={gap:+.3f}  {r['title'][:50]}")

    print("\nNever a candidate at any score (not fixable by threshold alone):")
    for r in unrecoverable:
        print(f"  [{r['category']:20s}] {r['concept']:12s}  {r['title'][:50]}")

    json.dump(results, open("data/evaluation/recall_ceiling_results.json", "w"), indent=2)


if __name__ == "__main__":
    main()
