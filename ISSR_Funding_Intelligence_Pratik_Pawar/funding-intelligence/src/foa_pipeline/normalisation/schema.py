from datetime import datetime, timezone
from typing import Any, Dict, Optional

SCHEMA_VERSION = "1.0"

# Valid enum values for the canonical schema
VALID_SOURCES = ("grants_gov", "nsf_scraper", "pdf_upload")
VALID_STATUSES = ("open", "closed", "forecasted", "archived")
VALID_FUNDING_INSTRUMENTS = ("grant", "cooperative_agreement", "procurement_contract", "other")
VALID_TAG_CATEGORIES = ("research_domain", "method", "population", "sponsor_theme")
VALID_SOURCE_LAYERS = ("layer_1_terminological", "layer_2_embedding", "layer_3_llm")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_raw_record(
    *,
    source: str,
    source_id: str,
    title: Optional[str],
    posted_date: Optional[str],
    close_date: Optional[str],
    raw_url: Optional[str],
    raw_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a raw ingestion record (v0.1 compat, used by grants_gov.py)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "source_id": source_id,
        "title": title,
        "posted_date": posted_date,
        "close_date": close_date,
        "raw_url": raw_url,
        "fetched_at": _iso_now(),
        "raw_payload": raw_payload,
    }
