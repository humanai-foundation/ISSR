"""
JSON export of the tagged FOA dataset.

The scope of work asks for the dataset to be deliverable as **both** JSON and
CSV. Only CSV was previously written to disk; JSON existed solely as an API
response (`GET /api/export/json`), which requires running a server and so is not
a reproducible artefact a reviewer can regenerate and diff.

The two exports carry the same records but not the same shape, on purpose. CSV
is flattened for humans — tags collapsed into a pipe-separated column, the
description truncated — because it is opened in Excel by research development
officers. JSON keeps the full nested structure: complete descriptions, tags as
objects with their category, confidence, source layer and evidence snippet. It
is the machine-readable form, and the one to build on.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..normalisation.schema import SCHEMA_VERSION

logger = logging.getLogger(__name__)

SCHEMA_VERSION_KEY = "schema_version"


def build_export_payload(
    foa_records: List[Dict[str, Any]],
    include_raw_payload: bool = False,
) -> Dict[str, Any]:
    """
    Assemble the export document.

    `raw_payload` is dropped by default: it holds the untouched upstream API
    response, which is large, source-specific, and already preserved in
    `data/raw/*.jsonl`. Including it would roughly triple the file and blur what
    the canonical schema actually guarantees.
    """
    records: List[Dict[str, Any]] = []
    for record in foa_records:
        clean = {k: v for k, v in record.items() if include_raw_payload or k != "raw_payload"}
        records.append(clean)

    # Records read back via `list_foas` do not carry `schema_version` — the
    # column is written on ingest but not selected — so fall back to the
    # canonical constant rather than emitting an empty list and claiming the
    # export has no schema.
    schema_versions = sorted(
        {str(r.get(SCHEMA_VERSION_KEY)) for r in records if r.get(SCHEMA_VERSION_KEY)}
    )
    if not schema_versions:
        schema_version: Any = SCHEMA_VERSION
    elif len(schema_versions) == 1:
        schema_version = schema_versions[0]
    else:
        # Mixed versions are worth surfacing rather than silently picking one.
        schema_version = schema_versions

    tagged = sum(1 for r in records if r.get("tags"))

    return {
        "schema_version": schema_version,
        "record_count": len(records),
        "tagged_record_count": tagged,
        "foas": records,
    }


def export_foas_to_json(
    foa_records: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    include_raw_payload: bool = False,
) -> str:
    """
    Export FOA records to JSON.

    Returns the output path, or the JSON string when `output_path` is None.
    Keys are sorted and indentation is fixed so that re-exporting an unchanged
    dataset produces an identical file — a diff should mean the data changed,
    not that the exporter ran again.
    """
    payload = build_export_payload(foa_records, include_raw_payload=include_raw_payload)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str)

    if output_path is None:
        return text

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    logger.info(
        "Exported %d FOAs (%d tagged) to %s",
        payload["record_count"], payload["tagged_record_count"], path,
    )
    return str(path)
