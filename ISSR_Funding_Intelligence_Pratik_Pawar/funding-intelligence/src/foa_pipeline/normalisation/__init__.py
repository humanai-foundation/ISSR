"""Canonical schema: normalisation and JSON Schema validation."""

from .normaliser import normalise_record
from .schema import SCHEMA_VERSION, build_raw_record
from .validator import validate_batch, validate_record

__all__ = [
    "normalise_record",
    "validate_record",
    "validate_batch",
    "build_raw_record",
    "SCHEMA_VERSION",
]
