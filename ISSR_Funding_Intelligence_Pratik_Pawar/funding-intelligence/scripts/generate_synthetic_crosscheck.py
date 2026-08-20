"""
LLM-vs-human diagnostic cross-check on the expanded 40-FOA gold set.

IMPORTANT — this is NOT inter-annotator agreement. Comparing an LLM's labels
to a human's labels on the same FOAs validates the model against a human
baseline, not against a second independent human judgement. Documentation/EVALUATION.md 2
and Documentation/ONTOLOGY.md 7 are explicit that this exact comparison already exists once
(the eval_set_50.json spot-check) and does not substitute for a genuine
second annotator. This script produces a second, honestly-labelled instance
of that same kind of diagnostic -- now against the full 40-FOA gold set
instead of a 21-FOA "easy" subset -- and nothing here should be reported as
having closed the IAA gap. That still requires an independent human pass
(see Documentation/ANNOTATION_CODEBOOK.md).

Reuses the exact prompts, Ollama call, and full-list-echo guard from
synthetic_annotator.py (the same tool that built eval_set_50.json) rather
than reimplementing them, so this is methodologically identical to the
project's one existing precedent for this kind of comparison.

Output: data/evaluation/gold_expansion_synthetic_crosscheck.json -- one
entry per gold-set FOA (all 40, once the human packet is merged), each
carrying `synthetic_tags` (never `human_tags` -- there is no runner-
compatibility reason to keep that misnomer here) plus provenance.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, "src")

from foa_pipeline.config import get_config  # noqa: E402
from foa_pipeline.storage.database import Database  # noqa: E402
from foa_pipeline.evaluation.synthetic_annotator import (  # noqa: E402
    CATEGORY_PROMPTS,
    call_ollama,
    get_concepts_by_category,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

GOLD_PATH = "data/evaluation/eval_set_gold.json"
CANDIDATES_PATH = "data/evaluation/gold_expansion_candidates.json"
OUT_PATH = "data/evaluation/gold_expansion_synthetic_crosscheck.json"


def load_targets(db: Database) -> list[dict]:
    """All 40 gold-set FOA IDs (original 20 + the new 20 candidates), with
    full text pulled fresh from the DB -- eval_set_gold.json itself only
    stores foa_id/title/human_tags/rationale, not the description fields."""
    gold_ids = [e["foa_id"] for e in json.loads(Path(GOLD_PATH).read_text())]
    candidate_ids = [e["foa_id"] for e in json.loads(Path(CANDIDATES_PATH).read_text())]
    all_ids = gold_ids + candidate_ids

    targets = []
    cur = db.conn.cursor()
    for foa_id in all_ids:
        cur.execute(
            "SELECT foa_id, title, program_description, eligibility_description, additional_info "
            "FROM foa_records WHERE foa_id = ?",
            (foa_id,),
        )
        row = cur.fetchone()
        if row is None:
            logging.warning("FOA %s not found in DB, skipping", foa_id)
            continue
        targets.append(dict(row))
    return targets


def annotate(foa: dict, concepts_by_cat: dict, base_url: str, model: str) -> dict:
    text_parts = [
        foa.get("title", ""),
        foa.get("program_description", "") or "",
        foa.get("eligibility_description", "") or "",
        foa.get("additional_info", "") or "",
    ]
    text = " ".join(p for p in text_parts if p)[:4000]

    all_tags: list[str] = []
    for cat, concepts in concepts_by_cat.items():
        if cat not in CATEGORY_PROMPTS:
            continue
        concept_list = "\n".join(f"- {c['id']}: {c['label']}" for c in concepts)
        prompt = CATEGORY_PROMPTS[cat].format(concepts=concept_list, text=text)
        tags = call_ollama(base_url, model, prompt)

        valid_ids = {c["id"] for c in concepts}
        validated = list(dict.fromkeys(t for t in tags if t in valid_ids))

        if len(valid_ids) >= 4 and len(validated) > 0.5 * len(valid_ids):
            logging.warning(
                "  [%s] discarded %d/%d concepts (full-list echo)",
                cat, len(validated), len(valid_ids),
            )
            continue
        all_tags.extend(validated)

    return {
        "foa_id": foa["foa_id"],
        "title": foa["title"],
        "synthetic_tags": all_tags,
        "annotation_provenance": {"model": model, "source": "synthetic_crosscheck"},
    }


def main() -> None:
    config = get_config()
    db = Database(config.app_db_path)
    concepts_by_cat = get_concepts_by_category(db)
    targets = load_targets(db)

    logging.info("Cross-checking %d FOAs with %s", len(targets), config.ollama_model)

    results = []
    for i, foa in enumerate(targets):
        logging.info("[%d/%d] %s", i + 1, len(targets), foa["title"][:70])
        results.append(annotate(foa, concepts_by_cat, config.ollama_base_url, config.ollama_model))
        if (i + 1) % 5 == 0:
            Path(OUT_PATH).write_text(json.dumps(results, indent=2))

    Path(OUT_PATH).write_text(json.dumps(results, indent=2))
    logging.info("Wrote %d entries to %s", len(results), OUT_PATH)


if __name__ == "__main__":
    main()
