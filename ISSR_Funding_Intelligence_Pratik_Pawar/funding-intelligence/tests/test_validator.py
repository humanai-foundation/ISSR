"""Tests for the validator module."""

from foa_pipeline.normalisation.validator import (
    SCHEMA_PATH,
    _minimal_schema,
    load_schema,
    validate_batch,
    validate_record,
)


class TestSchemaIsActuallyLoaded:
    """
    The real Draft-7 schema must be found on disk.

    When it is not, `load_schema` silently falls back to a permissive minimal
    schema and validation quietly stops enforcing 20 of 27 properties. That
    happened for real: the package restructure moved this module one directory
    deeper and the hard-coded parent hops began resolving to `src/data/`. Every
    record still "validated", so nothing failed — the only symptom was a log
    line. None of the tests below caught it, because the fallback duplicates
    exactly the fields they exercise.
    """

    def test_schema_file_is_found(self):
        assert SCHEMA_PATH.exists(), (
            f"Schema not found at {SCHEMA_PATH}. Validation has silently "
            "degraded to the minimal fallback."
        )

    def test_loaded_schema_is_the_real_one_not_the_fallback(self):
        real, minimal = load_schema(), _minimal_schema()
        assert set(real["properties"]) - set(minimal["properties"]), (
            "load_schema() returned the minimal fallback"
        )
        assert len(real["properties"]) >= 25

    def test_fields_only_the_real_schema_constrains_are_enforced(self, sample_foa):
        """A money field the fallback does not know about at all."""
        sample_foa["award_ceiling"] = -5
        is_valid, errors = validate_record(sample_foa)
        assert not is_valid
        assert any("award_ceiling" in e for e in errors)

    def test_negative_award_floor_is_rejected(self, sample_foa):
        sample_foa["award_floor"] = -1
        is_valid, _ = validate_record(sample_foa)
        assert not is_valid

    def test_wrong_type_in_an_unvalidated_field_is_caught(self, sample_foa):
        sample_foa["agency"] = 12345
        is_valid, _ = validate_record(sample_foa)
        assert not is_valid


def test_valid_record(sample_foa):
    is_valid, errors = validate_record(sample_foa)
    assert is_valid, f"Validation errors: {errors}"
    assert errors == []


def test_missing_required_field():
    record = {"schema_version": "1.0", "source": "grants_gov"}
    is_valid, errors = validate_record(record)
    assert not is_valid
    assert len(errors) > 0


def test_invalid_status(sample_foa):
    sample_foa["status"] = "invalid_status"
    is_valid, errors = validate_record(sample_foa)
    assert not is_valid


def test_empty_title(sample_foa):
    sample_foa["title"] = ""
    is_valid, errors = validate_record(sample_foa)
    assert not is_valid


def test_batch_validation(sample_foa):
    good = sample_foa.copy()
    bad = {"schema_version": "1.0"}  # Missing required fields

    results = validate_batch([good, bad])
    assert results["total"] == 2
    assert results["valid"] == 1
    assert results["invalid"] == 1
    assert len(results["errors"]) == 1
