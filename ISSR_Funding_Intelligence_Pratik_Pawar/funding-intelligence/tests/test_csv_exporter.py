"""Tests for the CSV exporter module."""

import csv
import io
import os

import pytest

from foa_pipeline.export.csv_exporter import export_foas_to_csv


@pytest.fixture
def tagged_foa():
    """A FOA record with tags for export testing."""
    return {
        "schema_version": "1.0",
        "foa_id": "export-test-001",
        "source": "grants_gov",
        "source_id": "999",
        "source_url": "https://grants.gov/view/999",
        "title": "Rural Health Disparities Research",
        "agency": "National Institutes of Health",
        "agency_code": "NIH",
        "opportunity_number": "NIH-25-001",
        "cfda_numbers": ["93.310"],
        "posted_date": "2025-06-01",
        "close_date": "2025-12-31",
        "archive_date": None,
        "status": "open",
        "funding_instrument": "grant",
        "award_floor": 100000.0,
        "award_ceiling": 500000.0,
        "expected_awards": 5,
        "estimated_funding": 2500000.0,
        "eligibility": ["Universities", "Non-profits"],
        "program_description": "This program funds research on health disparities.",
        "eligibility_description": "Open to institutions of higher education.",
        "additional_info": None,
        "tags": [
            {
                "tag_id": "layer_1_terminological:sdg_03",
                "label": "Good Health and Well-being",
                "category": "research_domain",
                "source_layer": "layer_1_terminological",
                "confidence": 1.0,
                "context_snippet": "health disparities in rural communities",
                "ontology_concept_id": "sdg_03",
            },
            {
                "tag_id": "layer_2_embedding:meth_survey",
                "label": "Survey Research",
                "category": "method",
                "source_layer": "layer_2_embedding",
                "confidence": 0.82,
                "context_snippet": "survey-based study of health outcomes",
                "ontology_concept_id": "meth_survey",
            },
        ],
        "ingestion_date": "2025-06-01T00:00:00Z",
        "last_updated": "2025-06-01T00:00:00Z",
        "raw_payload": {},
    }


@pytest.fixture
def foa_no_tags(sample_foa):
    """A FOA record with no tags."""
    return sample_foa  # sample_foa from conftest already has tags=[]


class TestExportToString:
    """Test exporting FOAs to CSV string (no file)."""

    def test_export_single_record(self, tagged_foa):
        """Export a single tagged FOA to CSV string."""
        csv_str = export_foas_to_csv([tagged_foa])
        assert isinstance(csv_str, str)
        assert len(csv_str) > 0

    def test_correct_columns(self, tagged_foa):
        """Verify all expected CSV columns are present."""
        csv_str = export_foas_to_csv([tagged_foa])
        reader = csv.DictReader(io.StringIO(csv_str))
        headers = reader.fieldnames
        expected = [
            "foa_id", "title", "agency", "agency_code",
            "opportunity_number", "posted_date", "close_date", "status",
            "award_floor", "award_ceiling", "estimated_funding",
            "eligibility", "program_description", "tags", "tag_evidence",
            "source_url", "ingestion_date", "schema_version",
        ]
        for col in expected:
            assert col in headers, f"Missing column: {col}"

    def test_tags_column_has_pipe_separated_labels(self, tagged_foa):
        """Verify tags column contains pipe-separated labels."""
        csv_str = export_foas_to_csv([tagged_foa])
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        assert "Good Health and Well-being" in row["tags"]
        assert "Survey Research" in row["tags"]
        assert "|" in row["tags"]

    def test_tag_evidence_has_layer_and_confidence(self, tagged_foa):
        """Verify tag_evidence column includes layer info and confidence."""
        csv_str = export_foas_to_csv([tagged_foa])
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        evidence = row["tag_evidence"]
        assert "layer_1_terminological" in evidence
        assert "layer_2_embedding" in evidence
        assert "1.00" in evidence
        assert "0.82" in evidence

    def test_empty_tags(self, foa_no_tags):
        """FOA with no tags should have empty tags and tag_evidence."""
        csv_str = export_foas_to_csv([foa_no_tags])
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        assert row["tags"] == ""
        assert row["tag_evidence"] == ""

    def test_eligibility_semicolon_separated(self, tagged_foa):
        """Eligibility list should be semicolon-separated."""
        csv_str = export_foas_to_csv([tagged_foa])
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        assert "Universities" in row["eligibility"]
        assert "Non-profits" in row["eligibility"]
        assert ";" in row["eligibility"]

    def test_description_truncated(self, tagged_foa):
        """Program description should be truncated to 500 chars."""
        long_desc = "x" * 1000
        tagged_foa["program_description"] = long_desc
        csv_str = export_foas_to_csv([tagged_foa])
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        assert len(row["program_description"]) == 500

    def test_empty_records_list(self):
        """Exporting empty list should produce CSV with headers only."""
        csv_str = export_foas_to_csv([])
        lines = csv_str.strip().split("\n")
        assert len(lines) == 1  # Header row only

    def test_multiple_records(self, tagged_foa, foa_no_tags):
        """Export multiple records."""
        csv_str = export_foas_to_csv([tagged_foa, foa_no_tags])
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2


class TestExportToFile:
    """Test exporting FOAs to a CSV file."""

    def test_export_creates_file(self, tagged_foa, tmp_path):
        """Export should create a file at the specified path."""
        out_path = str(tmp_path / "test_export.csv")
        result = export_foas_to_csv([tagged_foa], output_path=out_path)
        assert result == out_path
        assert os.path.exists(out_path)

    def test_exported_file_is_valid_csv(self, tagged_foa, tmp_path):
        """Exported file should be valid CSV with correct number of rows."""
        out_path = str(tmp_path / "test_export.csv")
        export_foas_to_csv([tagged_foa], output_path=out_path)
        with open(out_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["foa_id"] == "export-test-001"
