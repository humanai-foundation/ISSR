"""
NSF Award Search connector — an agency-labelled evaluation corpus.

This is deliberately *not* an FOA source, and harvested records must never be
written into `foa_records`. Awards and solicitations are different genres: an
award describes work that was funded, in the past tense and with results
promised; an FOA solicits it, and carries eligibility, deadlines and submission
mechanics that awards have none of. Mixing them would pollute the FOA corpus and
quietly change what the search index means.

What this *is*: a free source of research abstracts whose discipline label was
assigned by NSF itself. The hand-labelled gold set is 20 FOAs — far too small to
say anything confident about `research_discipline` per-concept, where a single
tag decision moves F1 by more than the effects being measured. This corpus is
thousands of documents at zero annotation cost, which is the only realistic way
to get measurement resolution on that category before the GSoC deadline.

Its limitation must be stated wherever its numbers are: the genre shift above is
real, so accuracy here is a *complementary* benchmark and not a substitute for
the gold set. It answers "can Layer 2 separate the eight NSF directorates given
clean research prose", not "does the tagger work on FOAs".

API notes, all verified against the live service rather than the documentation:
  - No authentication, no API key.
  - `rpp` (results per page) caps at 25; `offset` is 1-based.
  - A single query returns at most 3,000 results, hence the CFDA x year
    partitioning in `harvest_awards`.
  - `printFields` is accepted but ignored — the full record comes back anyway.
  - The abbreviation for Computer & Information Science is `CSE`, *not* `CISE`,
    and the Office of the Director's is `O/D` with a slash. Deriving concept IDs
    from abbreviations would therefore be wrong twice, which is why the
    crosswalks below are explicit.
"""

import datetime as _dt
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from ..config import Config
from ..storage.jsonl import ensure_dir, load_existing_ids, write_jsonl

logger = logging.getLogger(__name__)

NSF_AWARDS_URL = "https://api.nsf.gov/services/v1/awards.json"

# The service refuses larger pages; asking for more silently returns 25.
MAX_RESULTS_PER_PAGE = 25

# A single query cannot page past this, regardless of how many awards match.
MAX_RESULTS_PER_QUERY = 3000

# Directorate abbreviation -> ontology concept. Enumerated from 600 awards
# sampled across 2010-2025; these nine are the complete observed set.
DIRECTORATE_ABBR_TO_CONCEPT: Dict[str, Optional[str]] = {
    "BIO": "nsf_bio",
    "CSE": "nsf_cise",     # note: not "CISE"
    "EDU": "nsf_edu",
    "EHR": "nsf_edu",      # pre-2023 name for the same directorate
    "ENG": "nsf_eng",
    "GEO": "nsf_geo",
    "MPS": "nsf_mps",
    "SBE": "nsf_sbe",
    "TIP": "nsf_tip",
    # Not a research directorate. Mapping it to any discipline would be
    # inventing a label, so it is skipped and counted instead.
    "O/D": None,
}

# Full organisation name -> concept, used when `dirAbbr` is missing. Matched
# case-insensitively after whitespace collapsing.
DIRECTORATE_NAME_TO_CONCEPT: Dict[str, Optional[str]] = {
    "directorate for biological sciences": "nsf_bio",
    "directorate for computer and information science and engineering": "nsf_cise",
    "directorate for stem education": "nsf_edu",
    "directorate for education and human resources": "nsf_edu",
    "directorate for engineering": "nsf_eng",
    "directorate for geosciences": "nsf_geo",
    "directorate for mathematical and physical sciences": "nsf_mps",
    "directorate for social, behavioral and economic sciences": "nsf_sbe",
    "directorate for technology, innovation, and partnerships": "nsf_tip",
    "office of the director": None,
}

# CFDA (Assistance Listing) number -> concept. Every entry was verified by
# querying the number and confirming that awards carrying it alone agree
# unanimously on `dirAbbr`; see the module tests. Polar Programs (47.078)
# resolves to Geosciences, which is where it now sits organisationally.
CFDA_TO_CONCEPT: Dict[str, Optional[str]] = {
    "47.041": "nsf_eng",
    "47.049": "nsf_mps",
    "47.050": "nsf_geo",
    "47.070": "nsf_cise",
    "47.074": "nsf_bio",
    "47.075": "nsf_sbe",
    "47.076": "nsf_edu",
    "47.078": "nsf_geo",   # Polar Programs
    "47.084": "nsf_tip",
    # Cross-cutting offices with no single discipline: International Science &
    # Engineering and Integrative Activities (EPSCoR). Both report `O/D`.
    "47.079": None,
    "47.083": None,
}

# The CFDA numbers worth partitioning a harvest across — those that carry a
# discipline. Ordered so the smallest directorates are fetched first, which
# makes an interrupted harvest more balanced than fetching MPS to exhaustion.
HARVEST_CFDA_NUMBERS: Tuple[str, ...] = (
    "47.084",  # TIP
    "47.076",  # EDU
    "47.075",  # SBE
    "47.078",  # GEO (Polar)
    "47.070",  # CISE
    "47.074",  # BIO
    "47.050",  # GEO
    "47.041",  # ENG
    "47.049",  # MPS
)


def _normalise_name(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def parse_cfda_numbers(raw: Optional[str]) -> List[str]:
    """
    Split the `cfdaNumber` field, which holds a comma-separated list.

    Co-funded awards carry more than one — "47.041, 47.070" is an award funded
    jointly by Engineering and CISE. Treating that string as a single key would
    silently drop every co-funded award from the crosswalk.
    """
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def directorate_to_concept(
    abbr: Optional[str], long_name: Optional[str] = None
) -> Optional[str]:
    """
    Map an award's managing directorate to an ontology concept.

    Returns None for anything unrecognised or for organisations that are not
    research directorates. Callers must treat None as "no label available" and
    exclude the award — guessing a discipline here would fabricate ground truth,
    which is the one thing an evaluation corpus cannot afford.
    """
    if abbr:
        key = abbr.strip().upper()
        if key in DIRECTORATE_ABBR_TO_CONCEPT:
            return DIRECTORATE_ABBR_TO_CONCEPT[key]
        logger.debug("Unrecognised NSF directorate abbreviation: %r", abbr)

    if long_name:
        return DIRECTORATE_NAME_TO_CONCEPT.get(_normalise_name(long_name))

    return None


def acceptable_concepts(
    primary: Optional[str], cfda_numbers: Sequence[str]
) -> List[str]:
    """
    The full set of discipline labels an award can fairly be credited with.

    `dirAbbr` names only the *managing* directorate. A co-funded award is
    genuinely interdisciplinary, so scoring a prediction of its co-funding
    directorate as wrong would penalise the tagger for being right. Evaluation
    should report strict accuracy (against `primary`) alongside lenient accuracy
    (against this set) rather than silently picking one.
    """
    concepts: List[str] = []
    if primary:
        concepts.append(primary)
    for number in cfda_numbers:
        concept = CFDA_TO_CONCEPT.get(number)
        if concept and concept not in concepts:
            concepts.append(concept)
    return concepts


def build_award_record(award: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert a raw API award into an evaluation-corpus record.

    Returns None when the award cannot serve as labelled data — no abstract, or
    no directorate that maps to a discipline.
    """
    abstract = (award.get("abstractText") or "").strip()
    award_id = str(award.get("id") or "").strip()
    if not award_id or not abstract:
        return None

    abbr = award.get("dirAbbr")
    long_name = award.get("orgLongName")
    primary = directorate_to_concept(abbr, long_name)
    if not primary:
        return None

    cfda_numbers = parse_cfda_numbers(award.get("cfdaNumber"))

    return {
        "award_id": award_id,
        "title": (award.get("title") or "").strip(),
        "abstract": abstract,
        "primary_concept_id": primary,
        "acceptable_concept_ids": acceptable_concepts(primary, cfda_numbers),
        "directorate_abbr": abbr,
        "directorate_name": long_name,
        "division_name": award.get("orgLongName2"),
        "cfda_numbers": cfda_numbers,
        "program_name": award.get("fundProgramName"),
        "award_date": award.get("date"),
        "source": "nsf_awards",
    }


class NSFAwardsClient:
    """Paginating client for the NSF Award Search API."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        backoff = 1.0
        max_backoff = 30.0
        retries = 5

        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(NSF_AWARDS_URL, params=params, timeout=45)
            except requests.RequestException as exc:
                logger.warning("NSF awards request failed (%s/%s): %s", attempt, retries, exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Retryable status %s from NSF awards API (%s/%s)",
                    response.status_code,
                    attempt,
                    retries,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                # A truncated body is transient; retry rather than aborting the
                # whole harvest on one bad page.
                logger.warning("Malformed JSON from NSF awards API (%s/%s): %s",
                               attempt, retries, exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

        raise RuntimeError(f"NSF awards request failed after {retries} attempts")

    def iter_awards(
        self,
        date_start: str,
        date_end: str,
        cfda_number: Optional[str] = None,
        max_results: int = MAX_RESULTS_PER_QUERY,
        rate_limit: float = 0.25,
    ) -> List[Dict[str, Any]]:
        """
        Page through one query's results.

        Dates are MM/DD/YYYY, matching the API. `max_results` is clamped to the
        service's own 3,000-result ceiling — paging past it returns empty pages,
        not more data.
        """
        limit = min(max_results, MAX_RESULTS_PER_QUERY)
        collected: List[Dict[str, Any]] = []
        offset = 1

        while len(collected) < limit:
            params: Dict[str, Any] = {
                "dateStart": date_start,
                "dateEnd": date_end,
                "rpp": MAX_RESULTS_PER_PAGE,
                "offset": offset,
            }
            if cfda_number:
                params["cfdaNumber"] = cfda_number

            payload = self._get(params)
            awards = payload.get("response", {}).get("award", [])
            if not isinstance(awards, list) or not awards:
                break

            collected.extend(awards)
            if len(awards) < MAX_RESULTS_PER_PAGE:
                break

            offset += MAX_RESULTS_PER_PAGE
            if rate_limit:
                time.sleep(rate_limit)

        return collected[:limit]


def harvest_awards(
    config: Config,
    *,
    date_start: str = "01/01/2023",
    date_end: str = "12/31/2025",
    per_directorate: int = 200,
    cfda_numbers: Sequence[str] = HARVEST_CFDA_NUMBERS,
    rate_limit: float = 0.25,
) -> Dict[str, Any]:
    """
    Harvest a directorate-balanced award corpus into the evaluation directory.

    Partitioning by CFDA number rather than taking one undifferentiated sample
    is what makes this usable as a benchmark: NSF funds MPS and BIO far more
    heavily than TIP, so an unpartitioned sample would be dominated by two
    directorates and per-concept accuracy for the rest would rest on a handful
    of documents. Capping each partition at `per_directorate` also sidesteps the
    3,000-result query ceiling entirely.

    Writes to `evaluation_dir/nsf_awards.jsonl`, never to `foa_records` — see
    the module docstring for why that separation is load-bearing.
    """
    client = NSFAwardsClient(config)
    ensure_dir(config.evaluation_dir)
    output_path = config.evaluation_dir / "nsf_awards.jsonl"

    existing_ids = load_existing_ids(output_path)
    logger.info("Loaded %s existing NSF award IDs", len(existing_ids))

    per_concept: Dict[str, int] = {}
    skipped_unlabelled = 0
    skipped_duplicate = 0
    total_written = 0

    for cfda in cfda_numbers:
        awards = client.iter_awards(
            date_start=date_start,
            date_end=date_end,
            cfda_number=cfda,
            max_results=per_directorate,
            rate_limit=rate_limit,
        )
        logger.info("CFDA %s returned %s awards", cfda, len(awards))

        batch: List[Dict[str, Any]] = []
        for award in awards:
            record = build_award_record(award)
            if record is None:
                skipped_unlabelled += 1
                continue
            # `source_id` is what load_existing_ids reads, so the harvest is
            # resumable and re-runnable without duplicating rows.
            record["source_id"] = record["award_id"]
            if record["source_id"] in existing_ids:
                skipped_duplicate += 1
                continue

            record["harvested_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
            batch.append(record)
            existing_ids.add(record["source_id"])
            concept = record["primary_concept_id"]
            per_concept[concept] = per_concept.get(concept, 0) + 1

        if batch:
            total_written += write_jsonl(output_path, batch)

    return {
        "records_written": total_written,
        "skipped_unlabelled": skipped_unlabelled,
        "skipped_duplicate": skipped_duplicate,
        "per_concept": per_concept,
        "output_path": str(output_path),
    }
