"""
Generates data/evaluation/labeling_batch.csv -- binary relevance judgments
needed to get the cross-encoder reranker (Documentation/EVALUATION.md 4k, attempt 4) past
its data-volume ceiling. NOT full gold-standard annotation: one fast yes/no
judgment per (FOA, concept) candidate, not five-category tagging with
rationale. See data/evaluation/LABELING_INSTRUCTIONS.md for how to fill it
in.

Samples 300 FOAs not already reserved by the gold set or its in-progress
expansion, pulls Layer 2's method/population candidates at a threshold
below production (0.31/0.28 vs 0.40/0.35) -- deliberately including the
"gray zone" just under today's cutoff, since that's exactly where a
reranker's judgment would matter if the current threshold is wrong about a
given candidate.

Scores are deliberately NOT included in the output: showing the model's own
opinion while asking a human to judge relevance would anchor the label
toward confirming Layer 2 rather than giving an independent judgment, which
would defeat the point of using this as training signal Layer 2 doesn't
already encode.

Snippet extraction: candidate *selection* still runs through the normal
production tag_text() (same thresholds, same 231-FOA sample, same concept
list -- nothing about which candidates exist has changed). But the snippet
shown per candidate no longer reuses tag_text()'s own context_snippet
(Layer 2's 250-word chunking, chunk_size=250 in layer2_embedding.py).
Verified why that was wrong for this purpose: most FOA descriptions are
under 250 words (confirmed: a 159-word FOA produces exactly one chunk), so
every concept candidate for a document that short trivially shares the same
single chunk regardless of which part of the text actually supports it --
113 of the first 200 multi-candidate FOAs in the original batch had a
byte-identical snippet across every one of their candidate concepts. That's
not informative to a human judging relevance, and it isn't a
layer2_embedding.py bug either -- chunk_index really is the best-scoring
chunk, there just weren't enough chunks to distinguish between. Fixed here,
locally, without touching production chunking (which needs a full gold
before/after if it's ever changed): re-score at sentence granularity
(spaCy's blank-model sentencizer, no full NLP pipeline needed) purely to
pick which few sentences to display, so each candidate on the same FOA can
show genuinely different, concept-specific text.
"""

import csv
import json
import random
import sqlite3
import sys
from pathlib import Path

import numpy as np
import spacy

sys.path.insert(0, "src")

from foa_pipeline.config import get_config  # noqa: E402
from foa_pipeline.ontology.store import OntologyStore  # noqa: E402
from foa_pipeline.tagging.layer2_embedding import L2Tagger, cosine_similarity  # noqa: E402
from foa_pipeline.normalisation.boilerplate import strip_boilerplate  # noqa: E402

N_FOAS = 300
SEED = 7
THRESHOLDS = {"method": 0.31, "population": 0.28}
SENTENCE_WINDOW = 1  # sentences of context on each side of the best match
OUT_PATH = "data/evaluation/labeling_batch.csv"

_nlp = spacy.blank("en")
_nlp.add_pipe("sentencizer")


def split_sentences(text):
    return [s.text.strip() for s in _nlp(text).sents if s.text.strip()]


def best_sentence_snippet(sentences, sentence_embs, concept_emb, window=SENTENCE_WINDOW):
    if not sentences:
        return ""
    sims = [cosine_similarity(emb, concept_emb) for emb in sentence_embs]
    best_idx = int(np.argmax(sims))
    lo = max(0, best_idx - window)
    hi = min(len(sentences), best_idx + window + 1)
    return " ".join(sentences[lo:hi])


def main():
    config = get_config()
    store = OntologyStore(config.app_db_path)

    gold_ids = {e["foa_id"] for e in json.loads(Path("data/evaluation/eval_set_gold.json").read_text())}
    cand_ids = {e["foa_id"] for e in json.loads(Path("data/evaluation/gold_expansion_candidates.json").read_text())}
    excluded = gold_ids | cand_ids

    thresholds = dict(config.cosine_thresholds)
    thresholds.update(THRESHOLDS)
    l2 = L2Tagger(model_name=config.embedding_model, thresholds=thresholds, cache_dir=config.embeddings_cache_dir)
    l2.load_model()
    l2.build_embeddings(store)

    cur0 = store.conn.cursor()
    cur0.execute("SELECT concept_id, description FROM ontology_concepts")
    descriptions = {r["concept_id"]: (r["description"] or "") for r in cur0.fetchall()}

    con = sqlite3.connect(config.app_db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT foa_id, title, agency_code, program_description, "
        "eligibility_description, additional_info FROM foa_records"
    )
    rows = [dict(r) for r in cur.fetchall() if r["foa_id"] not in excluded]
    random.Random(SEED).shuffle(rows)
    sample = rows[:N_FOAS]

    output_rows = []
    for row in sample:
        head = strip_boilerplate(" ".join(p for p in (row["title"], row["program_description"]) if p))
        elig = strip_boilerplate(row["eligibility_description"] or "")
        tail = strip_boilerplate(row["additional_info"] or "")
        full_text = " ".join(s for s in (head, elig, tail) if s)
        if not full_text.strip():
            continue

        evidence = l2.tag_text(full_text, title=row["title"], title_weight=0.0)
        target_evidence = [ev for ev in evidence if ev.category in ("method", "population")]
        if not target_evidence:
            continue

        # Sentence-level re-scoring for snippet display only -- computed once
        # per FOA, reused across all of that FOA's candidate concepts, so
        # this doesn't multiply embedding cost per candidate.
        sentences = split_sentences(full_text)
        sentence_embs = l2.model.encode(sentences, convert_to_numpy=True) if sentences else []

        for ev in target_evidence:
            concept_emb = l2.concept_embeddings.get(ev.concept_id)
            snippet = (
                best_sentence_snippet(sentences, sentence_embs, concept_emb)
                if concept_emb is not None and len(sentences) > 0
                else ev.context_snippet
            )
            output_rows.append({
                "row_id": len(output_rows) + 1,
                "foa_id": row["foa_id"],
                "title": row["title"],
                "agency": row["agency_code"],
                "category": ev.category,
                "concept_id": ev.concept_id,
                "concept_label": ev.label,
                "concept_description": descriptions.get(ev.concept_id, ""),
                "text_snippet": snippet,
                "relevant_yes_no": "",
            })

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "row_id", "foa_id", "title", "agency", "category",
            "concept_id", "concept_label", "concept_description",
            "text_snippet", "relevant_yes_no",
        ])
        writer.writeheader()
        writer.writerows(output_rows)

    n_method = sum(1 for r in output_rows if r["category"] == "method")
    n_pop = sum(1 for r in output_rows if r["category"] == "population")
    print(f"Wrote {len(output_rows)} rows ({n_method} method, {n_pop} population) "
          f"from {len(sample)} FOAs to {OUT_PATH}")


if __name__ == "__main__":
    main()
