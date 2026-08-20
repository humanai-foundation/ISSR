"""
CSV export with tag_evidence column.

The CSV includes a tag_evidence column containing the exact text snippet
that triggered each tag — making the export directly usable by research
development officers at ISSR without any additional tooling.

Both outputs include ingestion_date and schema_version for full
reproducibility.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def export_foas_to_csv(
    foa_records: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """
    Export FOA records to CSV with tag evidence.

    Columns:
    - foa_id, title, agency, agency_code, opportunity_number
    - posted_date, close_date, status
    - award_floor, award_ceiling, estimated_funding
    - eligibility (semicolon-separated)
    - program_description (truncated to 500 chars)
    - tags (pipe-separated labels)
    - tag_evidence (pipe-separated context snippets with layer info)
    - source_url
    - ingestion_date, schema_version

    Args:
        foa_records: List of normalised FOA dicts
        output_path: Path to write CSV. If None, returns CSV as string.

    Returns:
        The output path or CSV string.
    """
    def get_aggregate_score(foa):
        tags = foa.get("tags", [])
        if not tags:
            return 0.0
        total_confidence = sum(t.get("confidence", 0.0) for t in tags)
        unique_categories = len(set(t.get("category", "") for t in tags if t.get("category")))
        return total_confidence * unique_categories

    # Sort FOAs by aggregate score (descending) so highest-quality matches float to the top
    sorted_foas = sorted(foa_records, key=get_aggregate_score, reverse=True)

    rows = []
    for foa in sorted_foas:
        tags = foa.get("tags", [])
        tag_labels = "|".join(t.get("label", "") for t in tags)
        tag_evidence = "|".join(
            f"[{t.get('source_layer', '')}:{t.get('confidence', 0):.2f}] "
            + (t.get('context_snippet', '') or '')
            .replace('\n', ' ')
            .replace('\r', '')
            .strip()[:200]
            for t in tags
        )

        # Structured eligibility codes when present, otherwise the prose the
        # source actually published. `list_foas` returns
        # `eligibility_description` and no `eligibility` key at all, so reading
        # only the latter left this column empty for every row in the export —
        # while 65 of 136 records held eligibility text the whole time. The
        # scope of work lists eligibility as a required field, so falling back
        # matters rather than being a nicety.
        eligibility = foa.get("eligibility") or []
        if isinstance(eligibility, list):
            eligibility_str = ";".join(str(e) for e in eligibility if e)
        else:
            eligibility_str = str(eligibility)

        if not eligibility_str:
            eligibility_str = (foa.get("eligibility_description") or "").strip()

        rows.append(
            {
                "foa_id": foa.get("foa_id"),
                "title": foa.get("title"),
                "agency": foa.get("agency"),
                "agency_code": foa.get("agency_code"),
                "opportunity_number": foa.get("opportunity_number"),
                "posted_date": foa.get("posted_date"),
                "close_date": foa.get("close_date"),
                "status": foa.get("status"),
                "award_floor": foa.get("award_floor"),
                "award_ceiling": foa.get("award_ceiling"),
                "estimated_funding": foa.get("estimated_funding"),
                "eligibility": eligibility_str,
                "program_description": (
                    foa.get("program_description") or ""
                )[:500],
                "tags": tag_labels,
                "tag_evidence": tag_evidence,
                "source_url": foa.get("source_url"),
                "ingestion_date": foa.get("ingestion_date"),
                "schema_version": foa.get("schema_version"),
            }
        )

    df = pd.DataFrame(rows)

    if output_path:
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info("Exported %d FOAs to %s", len(rows), output_path)
        return output_path
    else:
        return df.to_csv(index=False, encoding="utf-8")
