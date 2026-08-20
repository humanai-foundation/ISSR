"""
Synthetic Annotator — per-category prompting for the SILVER evaluation set.

Runs one focused prompt per ontology category rather than a single prompt
listing all 84 concepts. Each prompt then carries only 8-25 options, which a 7B
model handles far more reliably than one long list.

**These labels are not ground truth.** They are model-generated and belong to
the silver set (`eval_set_50.json`), which is used for tuning only. The gold set
(`eval_set_gold.json`) is hand-labelled and is the only thing reported as a
result. The field they are written to is called `human_tags` for backwards
compatibility with the evaluation runner, which is a misleading name — so every
annotated FOA also carries `annotation_provenance` recording which categories
came from a model, which model, and when. Do not conflate the two sets; see
Documentation/EVALUATION.md 2 and Documentation/ANNOTATION_CODEBOOK.md.

The known weakness of LLM annotation is domain expertise and rare classes,
which is exactly `method` and `population` here, so silver numbers should be
read as relative signal across configurations, never as absolute accuracy.
"""

import datetime as _dt
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from foa_pipeline.config import get_config
from foa_pipeline.storage.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


CATEGORY_PROMPTS = {
    "sponsor_theme": (
        "You are a US federal grants analyst. Read this grant program description and identify "
        "which GREAT Act mission categories apply. A category applies ONLY if the grant explicitly "
        "funds research or activities in that area.\n\n"
        "Available Categories:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"great_01\", \"great_05\"]\n"
        "JSON:"
    ),
    "research_domain": (
        "You are a UN Sustainable Development Goals expert. Read this grant program description "
        "and identify which UN SDGs are directly addressed. An SDG applies ONLY if the grant "
        "explicitly funds work related to that goal.\n\n"
        "Available SDGs:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"sdg_04\", \"sdg_13\"]\n"
        "JSON:"
    ),
    "method": (
        "You are a research methodology expert. Read this grant program description and identify "
        "which research methods are explicitly required or encouraged. A method applies ONLY if "
        "the grant specifically mentions or requires that research approach.\n\n"
        "Available Methods:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"method_01\", \"method_15\"]\n"
        "JSON:"
    ),
    "population": (
        "You are a demographics and equity expert. Read this grant program "
        "description and identify which target populations are explicitly "
        "mentioned as focus groups, beneficiaries, or required "
        "study subjects. A population applies ONLY if the grant explicitly targets that group.\n\n"
        "Available Populations:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"pop_03\", \"pop_12\"]\n"
        "JSON:"
    ),
    # Asks which directorate would *fund* the work rather than which topics are
    # mentioned. An FOA naming a review panel or citing a prior award drops many
    # directorate names it has nothing to do with, and "which topics appear"
    # would collect all of them.
    "research_discipline": (
        "You are an NSF programme officer. Read this grant program description and decide "
        "which NSF directorate would fund this research.\n\n"
        "Available Directorates:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Rules:\n"
        "- Choose based on the SUBJECT of the research, not on words that merely appear.\n"
        "- Most grants belong to exactly ONE directorate. Return two only for genuinely "
        "interdisciplinary programmes, and never more than two.\n"
        "- Choose STEM Education only when the research studies teaching or learning itself, "
        "not when a grant merely trains students or has education outreach.\n"
        "- Choose Technology Innovation and Partnerships only for commercialisation, "
        "technology transfer or industry partnership programmes.\n"
        "- If the description is too generic to tell, return [].\n\n"
        "Return a JSON list of the matching concept IDs. Example: [\"nsf_bio\"]\n"
        "JSON:"
    ),
}

# Maps a concept-ID prefix to its category, so an FOA's existing tags can be
# attributed to categories without a database round-trip. Used to decide which
# categories still need annotating.
PREFIX_TO_CATEGORY = {
    "great_": "sponsor_theme",
    "sdg_": "research_domain",
    "method_": "method",
    "pop_": "population",
    "nsf_": "research_discipline",
}


def _category_of(tag: Any) -> Optional[str]:
    """The ontology category a concept ID belongs to, by prefix."""
    for prefix, category in PREFIX_TO_CATEGORY.items():
        if str(tag).startswith(prefix):
            return category
    return None


def _record_provenance(
    existing: Optional[Dict[str, Any]], categories: Sequence[str], model: str
) -> Dict[str, Any]:
    """
    Note which categories were model-generated, by which model, and when.

    The labels live in a field called `human_tags` purely for backwards
    compatibility, so without this record there is nothing in the file itself
    distinguishing a model's guess from a person's judgement. Anyone reading
    `eval_set_50.json` in a year needs to be able to tell.
    """
    record: Dict[str, Any] = dict(existing or {})
    stamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for category in categories:
        record[category] = {"source": "llm", "model": model, "annotated_at": stamp}
    return record


def categories_present(tags: Iterable[Any]) -> set:
    """
    Which ontology categories a set of concept IDs already covers.

    Typed loosely because the tags come straight from a JSON file that is also
    hand-edited; a stray non-string should be ignored, not raise.
    """
    present = set()
    for tag in tags:
        for prefix, category in PREFIX_TO_CATEGORY.items():
            if str(tag).startswith(prefix):
                present.add(category)
                break
    return present


def get_concepts_by_category(db: Database):
    """Get all concepts grouped by category."""
    query = (
        "SELECT concept_id, label, category FROM ontology_concepts "
        "ORDER BY category, concept_id"
    )
    rows = db.conn.execute(query).fetchall()

    by_cat = {}
    for r in rows:
        cat = r["category"]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append({"id": r["concept_id"], "label": r["label"]})
    return by_cat


def call_ollama(base_url, model, prompt, max_retries=2):
    """Call Ollama with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.0, "num_predict": 256}
                },
                timeout=120.0
            )
            resp.raise_for_status()
            result_text = resp.json().get("response", "").strip()

            parsed = json.loads(result_text)

            # Handle dict responses. Two shapes observed from the model:
            #   {"tags": ["great_01", "great_05"]}        -> concept IDs in a list value
            #   {"great_05": ["chemical synthesis", ...]}  -> concept ID as the key itself
            # Collect candidates from both shapes; the caller filters against
            # valid_ids, so over-collecting here is harmless.
            if isinstance(parsed, dict):
                candidates = list(parsed.keys())
                for v in parsed.values():
                    if isinstance(v, list):
                        candidates.extend(str(x) for x in v)
                return candidates

            if isinstance(parsed, list):
                return [str(x) for x in parsed]

            return []

        except json.JSONDecodeError:
            if attempt < max_retries:
                logging.debug("JSON parse failed, retrying (%d/%d)", attempt + 1, max_retries)
                continue
            return []
        except Exception as e:
            if attempt < max_retries:
                logging.debug("Request error, retrying (%d/%d): %s", attempt + 1, max_retries, e)
                continue
            logging.error("Ollama call failed after %d attempts: %s", max_retries + 1, e)
            return []


def annotate_foas(categories: Optional[Sequence[str]] = None, overwrite: bool = False):
    """
    Annotate the silver evaluation set with model-generated labels.

    `categories` restricts the run to specific ontology categories. This exists
    because the set was originally annotated before `research_discipline` was
    added, leaving every FOA with tags in four categories and none in the fifth
    — and the original skip rule ("has any tags") would skip all of them
    forever. Passing a category annotates only FOAs missing *that* category,
    leaving existing labels untouched.

    `overwrite` re-annotates even where labels already exist, discarding the
    previous ones for the requested categories.
    """
    config = get_config()
    db = Database(config.app_db_path)

    eval_file = config.evaluation_dir / "eval_set_50.json"
    if not eval_file.exists():
        logging.error(f"{eval_file} not found. Run curate-eval-set first.")
        return

    with open(eval_file) as f:
        foas = json.load(f)

    concepts_by_cat = get_concepts_by_category(db)

    requested: List[str] = list(categories) if categories else list(CATEGORY_PROMPTS)
    unknown = [c for c in requested if c not in CATEGORY_PROMPTS]
    if unknown:
        raise ValueError(
            f"No prompt defined for {unknown}; known: {sorted(CATEGORY_PROMPTS)}"
        )

    base_url = config.ollama_base_url
    model = config.ollama_model

    logging.info(
        "Annotating %d FOAs using %s; categories=%s overwrite=%s",
        len(foas), model, requested, overwrite,
    )

    annotated_count = 0

    for i, foa in enumerate(foas):
        existing: List[str] = list(foa.get("human_tags") or [])
        have = categories_present(existing)

        todo = [c for c in requested if overwrite or c not in have]
        if not todo:
            logging.info(
                "[%d/%d] FOA %s: SKIPPED (already covers %s)",
                i + 1, len(foas), foa["foa_id"][:8], sorted(have & set(requested)),
            )
            continue

        # Build text from all available fields (enriched content)
        text_parts = [
            foa.get("title", ""),
            foa.get("program_description", ""),
            foa.get("eligibility_description", ""),
            foa.get("additional_info", ""),
        ]
        text = " ".join(p for p in text_parts if p)

        if not text.strip():
            # An FOA with no text cannot be annotated. Leave whatever labels it
            # already has alone — blanking them would destroy work from earlier
            # runs for a category this run was not even asked about.
            logging.warning(
                "[%d/%d] FOA %s: no text, skipping", i + 1, len(foas), foa["foa_id"][:8]
            )
            continue

        # Truncate to keep prompt manageable
        text_truncated = text[:4000]

        # Labels for categories this run is not touching are carried through
        # unchanged; only the requested ones are regenerated.
        kept = [t for t in existing if _category_of(t) not in todo]
        new_tags: List[str] = []

        for cat in todo:
            if cat not in concepts_by_cat:
                logging.warning("  [%s] no concepts in ontology, skipping", cat)
                continue

            concept_list = "\n".join(
                f"- {c['id']}: {c['label']}" for c in concepts_by_cat[cat]
            )

            prompt = CATEGORY_PROMPTS[cat].format(
                concepts=concept_list, text=text_truncated
            )

            tags = call_ollama(base_url, model, prompt)

            # Validate that returned tags are actual concept IDs in this category
            valid_ids = {c["id"] for c in concepts_by_cat[cat]}
            validated = list(dict.fromkeys(t for t in tags if t in valid_ids))

            # Sanity guard: a model that echoes back most/all of the category's
            # concept list (seen in practice on long/complex FOA text) is a
            # failure mode, not a genuine multi-label judgement. Discard it
            # rather than let it pollute the silver-standard set.
            if len(valid_ids) >= 4 and len(validated) > 0.5 * len(valid_ids):
                logging.warning(
                    "  [%s] discarded %d/%d concepts "
                    "(looks like a full-list echo, not a real selection)",
                    cat, len(validated), len(valid_ids),
                )
                continue

            new_tags.extend(validated)

        foa["human_tags"] = kept + new_tags
        foa["annotation_provenance"] = _record_provenance(
            foa.get("annotation_provenance"), todo, model
        )
        annotated_count += 1

        logging.info(
            "[%d/%d] FOA %s: +%s %s",
            i + 1, len(foas), foa["foa_id"][:8], todo, new_tags,
        )

        # Checkpoint every 5 FOAs
        if (i + 1) % 5 == 0:
            with open(eval_file, "w") as f:
                json.dump(foas, f, indent=2)

    # Final save
    with open(eval_file, "w") as f:
        json.dump(foas, f, indent=2)

    # Print summary
    labelled = sum(1 for f in foas if f.get("human_tags"))
    total_tags = sum(len(f.get("human_tags", [])) for f in foas)
    per_category: Dict[str, int] = {}
    for f in foas:
        for tag in f.get("human_tags") or []:
            cat = _category_of(tag)
            if cat:
                per_category[cat] = per_category.get(cat, 0) + 1

    logging.info(
        "Annotation complete: %d FOAs annotated this run; "
        "%d/%d labelled overall, %d total tags",
        annotated_count,
        labelled,
        len(foas),
        total_tags,
    )
    logging.info("Tags per category: %s", dict(sorted(per_category.items())))
    logging.info(
        "These are MODEL-generated silver labels, not ground truth. "
        "Report results on eval_set_gold.json only."
    )
    return {
        "annotated": annotated_count,
        "labelled": labelled,
        "total_tags": total_tags,
        "per_category": per_category,
    }


if __name__ == "__main__":
    annotate_foas()
