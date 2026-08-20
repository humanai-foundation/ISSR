import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests

from ..config import Config
from ..normalisation.schema import build_raw_record
from ..storage.jsonl import ensure_dir, load_existing_ids, write_jsonl

logger = logging.getLogger(__name__)


class GrantsGovClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.config.grants_gov_base_url}/{endpoint}"
        backoff = 1.0
        max_backoff = 30.0
        retries = 5

        for attempt in range(1, retries + 1):
            try:
                response = self.session.post(url, json=payload, timeout=30)
            except requests.RequestException as exc:
                logger.warning("Request failed (attempt %s/%s): %s", attempt, retries, exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Retryable status %s from %s (attempt %s/%s)",
                    response.status_code,
                    endpoint,
                    attempt,
                    retries,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

            response.raise_for_status()
            return response.json()

        raise RuntimeError(f"Grants.gov request failed after {retries} attempts")

    def search2(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(self.config.grants_gov_search_endpoint, payload)

    def fetch_opportunity(self, opportunity_id: str) -> Dict[str, Any]:
        return self._post(self.config.grants_gov_fetch_endpoint, {"opportunityId": opportunity_id})

    def download_attachment(self, att_id: str, output_path: Path) -> bool:
        """Download an attachment from Grants.gov to the specified path."""
        url = f"https://www.grants.gov/grantsws/rest/opportunity/synopsis/attachment/download?attId={att_id}"
        try:
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except requests.RequestException as exc:
            logger.warning("Failed to download attachment %s: %s", att_id, exc)
            return False


def _get_hit_value(hit: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if key in hit and hit[key]:
            return str(hit[key])
        lower_key = key.lower()
        for hit_key, value in hit.items():
            if hit_key.lower() == lower_key and value:
                return str(value)
    return None


def _iter_hits(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    data_block = payload.get("data", payload)
    hits = data_block.get("oppHits")
    if isinstance(hits, list):
        return hits
    hits = data_block.get("opportunities")
    if isinstance(hits, list):
        return hits
    return []


def poll_grants(config: Config, *, dry_run: bool = False) -> Dict[str, int]:
    client = GrantsGovClient(config)
    ensure_dir(config.raw_output_dir)
    output_path = config.raw_output_dir / "grants_gov.jsonl"

    existing_ids = load_existing_ids(output_path)
    logger.info("Loaded %s existing Grants.gov IDs", len(existing_ids))

    try:
        base_query = json.loads(config.grants_gov_query)
    except json.JSONDecodeError:
        logger.warning("GRANTS_GOV_QUERY is not valid JSON; defaulting to empty query")
        base_query = {}

    page_size = config.grants_gov_page_size
    start_record = 1
    pages = 0
    records_written = 0

    while True:
        pages += 1
        if config.grants_gov_max_pages and pages > config.grants_gov_max_pages:
            logger.info("Reached max pages: %s", config.grants_gov_max_pages)
            break

        query = dict(base_query)
        # The live search2 API silently ignores "numRecords" and always
        # returns 25 hits regardless of what's requested -- confirmed by
        # direct testing. "rows" is the parameter it actually honours
        # (verified up to 1000+ per page, disjoint across pages via
        # startRecordNum). With the wrong key, every poll silently capped
        # at 25 results and this loop's own "len(hits) < page_size" check
        # then terminated pagination after page 1, believing results were
        # exhausted.
        query.update({"startRecordNum": start_record, "rows": page_size})

        response = client.search2(query)
        hits = list(_iter_hits(response))
        if not hits:
            logger.info("No hits returned at page %s", pages)
            break

        new_records = []
        for hit in hits:
            opportunity_id = _get_hit_value(hit, "id", "OpportunityID", "opportunityId")
            if not opportunity_id or opportunity_id in existing_ids:
                continue

            details = {}
            if not dry_run:
                details = client.fetch_opportunity(opportunity_id)
                if config.grants_gov_request_delay_seconds > 0:
                    time.sleep(config.grants_gov_request_delay_seconds)

            record = build_raw_record(
                source="grants_gov",
                source_id=opportunity_id,
                title=_get_hit_value(hit, "title", "OpportunityTitle"),
                posted_date=_get_hit_value(hit, "openDate", "OpenDate", "postedDate"),
                close_date=_get_hit_value(hit, "closeDate", "CloseDate"),
                raw_url=_get_hit_value(hit, "url", "OpportunityURL"),
                raw_payload={"search_hit": hit, "details": details},
            )

            new_records.append(record)
            existing_ids.add(opportunity_id)

        if new_records and not dry_run:
            records_written += write_jsonl(output_path, new_records)

        if len(hits) < page_size:
            break

        start_record += page_size

    return {"pages": pages, "records_written": records_written}
