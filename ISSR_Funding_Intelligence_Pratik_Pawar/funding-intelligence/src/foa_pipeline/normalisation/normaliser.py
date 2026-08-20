"""
Data normalisation pipeline. Transforms raw ingested records (from Grants.gov,
NSF scraper, or PDF parser) into the canonical FOA schema.

Handles:
- Date harmonisation to ISO 8601
- HTML entity decoding
- Whitespace normalisation
- Award amount parsing (strip $, commas, handle ranges)
- Status inference from dates
- UUID generation for foa_id
"""

import html
import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from .schema import SCHEMA_VERSION

logger = logging.getLogger(__name__)


def normalise_record(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalise a raw record from any source into the canonical schema.

    Dispatches to source-specific extractors, then applies common
    normalisation (dates, whitespace, encoding).
    """
    if source == "grants_gov":
        return _normalise_grants_gov(raw)
    elif source == "nsf_scraper":
        return _normalise_nsf(raw)
    elif source == "pdf_upload":
        return _normalise_pdf(raw)
    else:
        raise ValueError(f"Unknown source: {source}")


# ═══════════════════════════════════════════════
# Common Normalisation Functions
# ═══════════════════════════════════════════════


def normalise_date(raw_date: Optional[str]) -> Optional[str]:
    """
    Parse various date formats into ISO 8601 (YYYY-MM-DD).

    Handles: 'MM/DD/YYYY', 'MMDDYYYY', 'Month DD, YYYY',
    'YYYY-MM-DD', epoch timestamps, etc.
    """
    if not raw_date:
        return None

    raw_date = str(raw_date).strip()
    if not raw_date:
        return None

    # Try ISO 8601 first
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d-%H-%M-%S",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%m%d%Y",
    ):
        try:
            return datetime.strptime(raw_date, fmt).date().isoformat()
        except ValueError:
            continue

    # Try epoch timestamp (Grants.gov sometimes uses ms timestamps)
    try:
        ts = int(raw_date)
        if ts > 1_000_000_000_000:  # milliseconds
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError):
        pass

    logger.warning("Unparseable date: %r", raw_date)
    return None


def normalise_text(text: Optional[str]) -> Optional[str]:
    """Strip HTML tags, decode HTML entities, normalise whitespace, strip."""
    if not text:
        return None
    text = str(text)
    # Strip HTML tags (handles <p>, <strong>, <span style="...">, etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities (&amp; → &, etc.)
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def parse_award_amount(raw: Optional[Any]) -> Optional[float]:
    """Parse dollar amounts: '$1,000,000' → 1000000.0"""
    if raw is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def infer_status(posted_date: Optional[str], close_date: Optional[str]) -> str:
    """Infer FOA status from dates."""
    today = date.today().isoformat()
    if close_date and close_date < today:
        return "closed"
    if posted_date and posted_date > today:
        return "forecasted"
    return "open"


def generate_foa_id() -> str:
    """Generate a unique FOA ID."""
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════
# Source-Specific Normalisers
# ═══════════════════════════════════════════════


GRANTS_GOV_DETAIL_URL = "https://www.grants.gov/search-results-detail/{opportunity_id}"


def grants_gov_detail_url(opportunity_id: Optional[Any]) -> Optional[str]:
    """
    Build the public Grants.gov page URL for an opportunity ID.

    The search API returns no link of any kind — `raw_url` is always None and
    the fetch payload's `assistURL` is empty — so without this every
    Grants.gov record had a null `source_url`, which the scope of work lists as
    a required field. That was 115 of 136 records.

    The pattern was verified rather than assumed: HTTP status alone proves
    nothing because the site is a single-page app that returns 200 for any
    path, including nonsense IDs. Confirmation came from fetching
    `/search-results-detail/362551` and finding opportunity number 26-511 in
    the response, matching what `fetchOpportunity` reports for that ID.
    """
    if opportunity_id in (None, ""):
        return None
    return GRANTS_GOV_DETAIL_URL.format(opportunity_id=str(opportunity_id).strip())


def _normalise_grants_gov(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalise fields from a Grants.gov raw record."""
    hit = raw.get("raw_payload", {}).get("search_hit", {})
    details = raw.get("raw_payload", {}).get("details", {})
    detail_data = details.get("data", {})
    # fetchOpportunity returns a "synopsis" object for docType=="synopsis"
    # (posted/closed) records, but a differently-shaped "forecast" object
    # instead for docType=="forecast" ones -- "synopsis" is simply absent,
    # not present-and-empty. Broadening the search query to oppStatuses
    # "forecasted|posted" (previously posted-only) surfaced this: every
    # field below silently went missing -- agency_code, award amounts,
    # eligibility, funding instrument -- for every forecasted record, since
    # they all read from `synopsis` alone. Most field names are identical
    # between the two shapes (agencyCode, awardFloor/Ceiling, numberOfAwards,
    # applicantTypes, applicantEligibilityDesc, fundingInstruments,
    # postingDate...), so falling back to "forecast" here recovers them.
    synopsis = detail_data.get("synopsis") or detail_data.get("forecast") or {}

    # Extract attachment IDs for PDF files
    att_folders = detail_data.get("synopsisAttachmentFolders", [])
    extracted_pdf_ids = []
    for folder in att_folders:
        for att in folder.get("synopsisAttachments", []):
            if att.get("mimeType") == "application/pdf" and att.get("id"):
                extracted_pdf_ids.append(str(att.get("id")))

    raw_payload_merged = raw.get("raw_payload", {})
    raw_payload_merged["extracted_pdf_ids"] = extracted_pdf_ids

    posted = normalise_date(
        _coalesce(
            raw.get("posted_date"),
            synopsis.get("postingDateStr"),
            synopsis.get("postingDate"),
        )
    )
    closed = normalise_date(
        _coalesce(
            raw.get("close_date"),
            synopsis.get("responseDateStr"),
            synopsis.get("responseDate"),
            # forecast-shaped records have no confirmed response date yet --
            # this is the closest honest equivalent (an estimate, since the
            # opportunity isn't open for applications until it's posted).
            synopsis.get("estApplicationResponseDateStr"),
            synopsis.get("estApplicationResponseDate"),
        )
    )

    # Safely extract first funding instrument if present
    funding_inst_list = synopsis.get("fundingInstruments", [])
    funding_inst_raw = funding_inst_list[0].get("description") if funding_inst_list else None

    return {
        "schema_version": SCHEMA_VERSION,
        "foa_id": generate_foa_id(),
        "source": "grants_gov",
        "source_id": str(raw.get("source_id", "")),
        "source_url": _coalesce(
            raw.get("raw_url"), grants_gov_detail_url(raw.get("source_id"))
        ),
        "title": normalise_text(_coalesce(raw.get("title"), synopsis.get("opportunityTitle"))),
        "agency": normalise_text(
            _coalesce(
                synopsis.get("agencyName"),
                # forecast-shaped records have no top-level agencyName, only
                # this nested form (present on both shapes where synopsis
                # has it too, so this is a safe fallback either way).
                detail_data.get("agencyDetails", {}).get("agencyName"),
                hit.get("agency"),
            )
        ),
        "agency_code": _coalesce(
            synopsis.get("agencyCode"), hit.get("agencyCode")
        ),
        "opportunity_number": _coalesce(
            detail_data.get("opportunityNumber"), hit.get("OpportunityNumber")
        ),
        "cfda_numbers": _extract_cfda(detail_data),
        "posted_date": posted,
        "close_date": closed,
        "archive_date": normalise_date(synopsis.get("archiveDateStr")),
        "status": infer_status(posted, closed),
        "funding_instrument": _map_funding_instrument(funding_inst_raw),
        "award_floor": parse_award_amount(synopsis.get("awardFloor")),
        "award_ceiling": parse_award_amount(synopsis.get("awardCeiling")),
        "expected_awards": _safe_int(synopsis.get("numberOfAwards")),
        "estimated_funding": parse_award_amount(
            synopsis.get("estimatedFunding")
        ),
        "eligibility": _extract_eligibility_types(synopsis),
        "program_description": normalise_text(
            _coalesce(
                synopsis.get("synopsisDesc"),
                synopsis.get("forecastDesc"),
                hit.get("Description"),
            )
        ),
        "eligibility_description": normalise_text(
            synopsis.get("applicantEligibilityDesc")
        ),
        "additional_info": normalise_text(synopsis.get("agencyContactDesc")),
        "tags": [],  # Populated by tagging pipeline
        "ingestion_date": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "raw_payload": raw_payload_merged,
    }


def _normalise_nsf(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalise fields from an NSF scraped record."""
    # The NSF scraper stores extracted fields inside raw_payload,
    # so we must fall through to raw_payload for every field.
    payload = raw.get("raw_payload", {})

    posted = normalise_date(
        _coalesce(raw.get("posted_date"), payload.get("posted_date"))
    )
    closed = normalise_date(
        _coalesce(raw.get("close_date"), payload.get("close_date"))
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "foa_id": generate_foa_id(),
        "source": "nsf_scraper",
        "source_id": str(
            _coalesce(raw.get("source_id"), payload.get("source_id"), "")
        ),
        "source_url": _coalesce(
            raw.get("source_url"), payload.get("source_url"), raw.get("raw_url")
        ),
        "title": normalise_text(
            _coalesce(raw.get("title"), payload.get("title"))
        ),
        "agency": "National Science Foundation",
        "agency_code": "NSF",
        "opportunity_number": _coalesce(
            raw.get("opportunity_number"), payload.get("opportunity_number")
        ),
        "cfda_numbers": raw.get("cfda_numbers", payload.get("cfda_numbers", [])),
        "posted_date": posted,
        "close_date": closed,
        "archive_date": None,
        "status": infer_status(posted, closed),
        "funding_instrument": "grant",
        "award_floor": parse_award_amount(
            _coalesce(raw.get("award_floor"), payload.get("award_floor"))
        ),
        "award_ceiling": parse_award_amount(
            _coalesce(raw.get("award_ceiling"), payload.get("award_ceiling"))
        ),
        "expected_awards": _safe_int(
            _coalesce(raw.get("expected_awards"), payload.get("expected_awards"))
        ),
        "estimated_funding": parse_award_amount(
            _coalesce(raw.get("estimated_funding"), payload.get("estimated_funding"))
        ),
        "eligibility": raw.get("eligibility", payload.get("eligibility", [])),
        "program_description": normalise_text(
            _coalesce(raw.get("program_description"), payload.get("program_description"))
        ),
        "eligibility_description": normalise_text(
            _coalesce(raw.get("eligibility_description"), payload.get("eligibility_description"))
        ),
        "additional_info": normalise_text(
            _coalesce(raw.get("additional_info"), payload.get("additional_info"))
        ),
        "tags": [],
        "ingestion_date": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        # Merge pdf_links to top-level of raw_payload so enrich-foas can find them
        "raw_payload": {
            **raw,
            "pdf_links": payload.get("pdf_links", []),
        },
    }


def _normalise_pdf(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalise fields from a parsed PDF FOA record."""
    posted = normalise_date(raw.get("posted_date"))
    closed = normalise_date(raw.get("close_date"))

    return {
        "schema_version": SCHEMA_VERSION,
        "foa_id": generate_foa_id(),
        "source": "pdf_upload",
        "source_id": str(raw.get("source_id", raw.get("source_path", ""))),
        "source_url": raw.get("source_url"),
        "title": normalise_text(raw.get("title")),
        "agency": normalise_text(raw.get("agency")),
        "agency_code": raw.get("agency_code"),
        "opportunity_number": raw.get("opportunity_number"),
        "cfda_numbers": raw.get("cfda_numbers", []),
        "posted_date": posted,
        "close_date": closed,
        "archive_date": None,
        "status": infer_status(posted, closed),
        "funding_instrument": _map_funding_instrument(
            raw.get("funding_instrument")
        ),
        "award_floor": parse_award_amount(raw.get("award_floor")),
        "award_ceiling": parse_award_amount(raw.get("award_ceiling")),
        "expected_awards": _safe_int(raw.get("expected_awards")),
        "estimated_funding": parse_award_amount(raw.get("estimated_funding")),
        "eligibility": raw.get("eligibility", []),
        "program_description": normalise_text(raw.get("program_description")),
        "eligibility_description": normalise_text(
            raw.get("eligibility_description")
        ),
        "additional_info": normalise_text(raw.get("additional_info")),
        "tags": [],
        "ingestion_date": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "raw_payload": raw,
    }


# ═══════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════


def _coalesce(*values: Any) -> Optional[Any]:
    """Return the first non-None, non-empty value."""
    for v in values:
        if v is not None and v != "":
            return v
    return None


def _extract_cfda(details: Dict) -> List[str]:
    """Extract CFDA/Assistance Listing numbers from details payload."""
    cfdas = details.get("cfdas", [])
    if isinstance(cfdas, list) and cfdas and isinstance(cfdas[0], dict):
        return [str(c.get("cfdaNumber")) for c in cfdas if c.get("cfdaNumber")]
    # Fallback for old formats
    cfda_str = _coalesce(
        details.get("cfdaNumber"),
        details.get("assistanceListingNumber"),
        details.get("cfda"),
    )
    if isinstance(cfda_str, str):
        return [c.strip() for c in cfda_str.split(";") if c.strip()]
    if isinstance(cfda_str, list):
        return [str(c) for c in cfda_str]
    return []


def _extract_eligibility_types(synopsis: Dict) -> List[str]:
    """Extract eligible applicant types."""
    elig = synopsis.get("applicantTypes", [])
    if isinstance(elig, list) and elig and isinstance(elig[0], dict):
        return [normalise_text(e.get("description")) for e in elig if e.get("description")]
    # Fallback
    elig_str = synopsis.get("eligibleApplicants")
    if isinstance(elig_str, list):
        return [normalise_text(e) for e in elig_str if e]
    if isinstance(elig_str, str):
        return [normalise_text(e) for e in elig_str.split(";") if e.strip()]
    return []


def _map_funding_instrument(raw: Optional[str]) -> Optional[str]:
    """Map raw funding instrument type to canonical enum."""
    if not raw:
        return None
    mapping = {
        "grant": "grant",
        "g": "grant",
        "cooperative agreement": "cooperative_agreement",
        "ca": "cooperative_agreement",
        "procurement contract": "procurement_contract",
        "pc": "procurement_contract",
    }
    return mapping.get(str(raw).lower().strip(), "other")


def _safe_int(val: Any) -> Optional[int]:
    """Safely convert to int."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
