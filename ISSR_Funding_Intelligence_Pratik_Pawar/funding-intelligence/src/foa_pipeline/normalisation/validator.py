"""
JSON Schema validation for FOA records.

Enforces:
- Required fields (foa_id, source, source_id, title, ingestion_date, status)
- ISO 8601 date formats
- Numeric award range fields
- Schema version consistency
- Valid enum values
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft7Validator, FormatChecker

logger = logging.getLogger(__name__)

def _find_schema() -> Path:
    """
    Locate `data/foa_schema.json` by walking up from this module.

    Previously a fixed number of `.parent` hops from `__file__`. Moving this
    module one directory deeper during the package restructure (41fb3ae) made
    that path resolve to `src/data/`, which does not exist — and the miss is
    silent, falling back to a permissive minimal schema. Draft-7 validation was
    therefore switched off for every record without a single error.

    Walking up removes the coupling between this file's depth and the path, so
    the same class of move cannot break it again.
    """
    for directory in Path(__file__).resolve().parents:
        candidate = directory / "data" / "foa_schema.json"
        if candidate.exists():
            return candidate
    # Return the conventional location so the warning names a useful path.
    return Path(__file__).resolve().parents[3] / "data" / "foa_schema.json"


SCHEMA_PATH = _find_schema()

_cached_schema: Optional[Dict[str, Any]] = None


def load_schema() -> Dict[str, Any]:
    """Load the FOA JSON Schema definition (cached after first load)."""
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema

    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            _cached_schema = json.load(f)
    else:
        logger.warning(
            "Schema file not found at %s; using minimal validation", SCHEMA_PATH
        )
        _cached_schema = _minimal_schema()

    return _cached_schema


def validate_record(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a single FOA record against the canonical schema.

    Returns:
        (is_valid, list_of_error_messages)
    """
    schema = load_schema()
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return (len(errors) == 0, errors)


def validate_batch(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate a batch of records. Returns summary stats.

    Returns:
        {
            "total": N,
            "valid": N,
            "invalid": N,
            "errors": [{"record_index": i, "foa_id": "...", "errors": [...]}]
        }
    """
    results: Dict[str, Any] = {
        "total": len(records),
        "valid": 0,
        "invalid": 0,
        "errors": [],
    }
    for i, record in enumerate(records):
        is_valid, errors = validate_record(record)
        if is_valid:
            results["valid"] += 1
        else:
            results["invalid"] += 1
            results["errors"].append(
                {
                    "record_index": i,
                    "foa_id": record.get("foa_id", "unknown"),
                    "errors": errors,
                }
            )
    return results


def _minimal_schema() -> Dict[str, Any]:
    """Fallback minimal schema when the full schema file is not found."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "schema_version",
            "foa_id",
            "source",
            "source_id",
            "title",
            "ingestion_date",
            "status",
        ],
        "properties": {
            "schema_version": {"type": "string"},
            "foa_id": {"type": "string"},
            "source": {"type": "string"},
            "source_id": {"type": "string"},
            "title": {"type": "string", "minLength": 1},
            "ingestion_date": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["open", "closed", "forecasted", "archived"],
            },
        },
    }
