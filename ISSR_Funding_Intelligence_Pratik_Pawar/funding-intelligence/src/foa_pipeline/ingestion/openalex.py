"""
OpenAlex taxonomy harvester — vendors the 26 Fields as a local CSV.

OpenAlex publishes a four-level research taxonomy (4 domains / 26 fields / 252
subfields / ~4,500 topics) under CC0. This module fetches the **field** level
once and writes it to `data/ontology/openalex_fields.csv`, so the pipeline never
depends on the API at runtime and the vendored file can be reviewed in a diff.

Why fields and not subfields: 26 concepts is roughly three times the eight NSF
directorates, which the 20-FOA gold set can plausibly be re-labelled against.
252 subfields cannot be evaluated at that sample size, so that level is
deliberately out of scope until the gold set grows.

**The vendored file is inert.** `OntologyStore.load_all_ontologies` reads an
explicit whitelist of filenames, and `openalex_fields.csv` is not on it. That is
intentional: adding a sixth category to the live ontology while no evaluation
set carries a single OpenAlex label would make every prediction in it a false
positive and collapse global gold F1 — the identical failure the silver set had
with `research_discipline`, documented in Documentation/EVALUATION.md 2. Registering the file
is a decision that has to follow labelling, not precede it.

Three things this data gives that the current ontology lacks:
  - `description` on every field, from an external authority rather than
    hand-written (see Documentation/EVALUATION.md 4f for why hand-written label text has a
    ceiling).
  - `display_name_alternatives`, a ready-made synonym set — 23 of 26 fields
    carry them, against 29 concepts in the current ontology that have none.
  - `domain`, a real parent, which would finally exercise the hierarchy
    propagation machinery that has been implemented and dormant.
"""

import csv
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

OPENALEX_FIELDS_URL = "https://api.openalex.org/fields"

# OpenAlex asks callers to identify themselves; doing so also routes the request
# to a faster, more reliable pool. Not authentication -- no key is involved.
DEFAULT_MAILTO = "pratikpawar1565@gmail.com"

VENDORED_FILENAME = "openalex_fields.csv"

CSV_COLUMNS = ("concept_id", "label", "category", "parent_id", "description", "synonyms")

# The category these concepts would occupy if the file were ever registered.
# Deliberately distinct from `research_discipline` so the two axes can be
# evaluated side by side rather than one silently replacing the other.
OPENALEX_CATEGORY = "openalex_field"

# Separator for the synonyms column. Commas are out because the values contain
# them ("Economics, Econometrics and Finance").
SYNONYM_SEPARATOR = "|"


def _entity_short_id(entity_id: str) -> str:
    """Turn 'https://openalex.org/fields/22' into '22'."""
    return str(entity_id).rstrip("/").rsplit("/", 1)[-1]


def field_concept_id(entity_id: str) -> str:
    return f"oa_field_{_entity_short_id(entity_id)}"


def domain_concept_id(entity_id: str) -> str:
    return f"oa_domain_{_entity_short_id(entity_id)}"


def fetch_fields(
    mailto: str = DEFAULT_MAILTO,
    timeout: float = 45.0,
    retries: int = 4,
) -> List[Dict[str, Any]]:
    """
    Fetch all 26 OpenAlex fields.

    All 26 fit in a single page, so there is no pagination to get wrong; the
    count is asserted by the caller rather than assumed here.
    """
    params = {"per-page": 50, "mailto": mailto}
    backoff = 1.0

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(OPENALEX_FIELDS_URL, params=params, timeout=timeout)
        except requests.RequestException as exc:
            logger.warning("OpenAlex request failed (%s/%s): %s", attempt, retries, exc)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue

        if response.status_code in (429, 500, 502, 503, 504):
            logger.warning(
                "Retryable status %s from OpenAlex (%s/%s)",
                response.status_code, attempt, retries,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue

        response.raise_for_status()
        return response.json().get("results", [])

    raise RuntimeError(f"OpenAlex fields request failed after {retries} attempts")


def build_field_rows(fields: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Convert API entities into ontology CSV rows.

    Rows are sorted by concept ID so that re-harvesting produces a stable file
    and a re-run shows an empty diff unless OpenAlex actually changed.
    """
    rows: List[Dict[str, str]] = []
    for field in fields:
        entity_id = field.get("id")
        if not entity_id:
            continue

        domain = field.get("domain") or {}
        alternatives = field.get("display_name_alternatives") or []

        rows.append({
            "concept_id": field_concept_id(entity_id),
            "label": field.get("display_name") or "",
            "category": OPENALEX_CATEGORY,
            # A real parent, unlike every concept currently in the ontology.
            "parent_id": domain_concept_id(domain["id"]) if domain.get("id") else "",
            "description": field.get("description") or "",
            "synonyms": SYNONYM_SEPARATOR.join(str(a) for a in alternatives),
        })

    rows.sort(key=lambda r: (len(r["concept_id"]), r["concept_id"]))
    return rows


def build_domain_rows(fields: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """The 4 parent domains, deduplicated from the fields' `domain` blocks."""
    seen: Dict[str, Dict[str, str]] = {}
    for field in fields:
        domain = field.get("domain") or {}
        if not domain.get("id"):
            continue
        concept_id = domain_concept_id(domain["id"])
        if concept_id not in seen:
            seen[concept_id] = {
                "concept_id": concept_id,
                "label": domain.get("display_name") or "",
                "category": OPENALEX_CATEGORY,
                "parent_id": "",
                "description": "",
                "synonyms": "",
            }
    return [seen[k] for k in sorted(seen)]


def write_ontology_csv(rows: List[Dict[str, str]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def harvest_openalex_fields(
    ontology_dir: Path,
    mailto: str = DEFAULT_MAILTO,
    include_domains: bool = True,
) -> Dict[str, Any]:
    """
    Fetch the OpenAlex field taxonomy and vendor it as a CSV.

    Writes to `ontology_dir/openalex_fields.csv`. The file is *not* loaded by
    `load_all_ontologies` — see the module docstring for why that separation is
    deliberate.
    """
    fields = fetch_fields(mailto=mailto)
    if not fields:
        raise RuntimeError("OpenAlex returned no fields")

    rows = build_domain_rows(fields) if include_domains else []
    domain_count = len(rows)
    rows = rows + build_field_rows(fields)

    output_path = ontology_dir / VENDORED_FILENAME
    written = write_ontology_csv(rows, output_path)

    with_synonyms = sum(1 for r in rows if r["synonyms"])
    logger.info(
        "Vendored %s rows to %s (%s domains, %s fields, %s with synonyms)",
        written, output_path, domain_count, len(rows) - domain_count, with_synonyms,
    )
    logger.info(
        "This file is NOT loaded by setup-ontology. Registering it before any "
        "eval set carries OpenAlex labels would collapse global gold F1."
    )

    return {
        "rows_written": written,
        "domains": domain_count,
        "fields": len(rows) - domain_count,
        "with_synonyms": with_synonyms,
        "output_path": str(output_path),
    }


def load_vendored_fields(ontology_dir: Path) -> List[Dict[str, str]]:
    """Read the vendored CSV back, for crosswalk validation and tests."""
    path = ontology_dir / VENDORED_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `cli harvest-openalex` first."
        )
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_synonyms(value: Optional[str]) -> List[str]:
    """Split the pipe-separated synonyms column."""
    if not value:
        return []
    return [part.strip() for part in value.split(SYNONYM_SEPARATOR) if part.strip()]
