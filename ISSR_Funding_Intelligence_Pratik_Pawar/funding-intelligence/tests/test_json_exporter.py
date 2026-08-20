"""
Tests for the JSON export and the two field gaps found auditing against the
project's scope of work.

All three defects here were silent: no error, no failing test, just a required
field quietly absent from the delivered dataset.
"""

import json

from foa_pipeline.export.csv_exporter import export_foas_to_csv
from foa_pipeline.export.json_exporter import build_export_payload, export_foas_to_json
from foa_pipeline.normalisation.normaliser import grants_gov_detail_url
from foa_pipeline.normalisation.schema import SCHEMA_VERSION


def _record(**overrides):
    record = {
        "foa_id": "abc-123",
        "title": "A programme",
        "agency": "National Science Foundation",
        "posted_date": "2026-01-01",
        "close_date": "2026-06-01",
        "program_description": "Research into things.",
        "eligibility_description": "Open to universities.",
        "source_url": "https://example.org/1",
        "tags": [{"label": "Engineering", "category": "research_discipline",
                  "confidence": 1.0, "source_layer": "layer_1_terminological"}],
    }
    record.update(overrides)
    return record


class TestGrantsGovSourceUrl:
    """
    The search API returns no link at all, so every Grants.gov record had a
    null `source_url` — 115 of 136 — against a field the scope of work
    requires.
    """

    def test_builds_the_detail_url(self):
        assert grants_gov_detail_url("362551") == (
            "https://www.grants.gov/search-results-detail/362551"
        )

    def test_accepts_an_integer_id(self):
        assert grants_gov_detail_url(362551).endswith("/362551")

    def test_strips_whitespace(self):
        assert grants_gov_detail_url(" 362551 ").endswith("/362551")

    def test_missing_id_yields_no_url(self):
        assert grants_gov_detail_url(None) is None
        assert grants_gov_detail_url("") is None


class TestCsvEligibilityFallback:
    """
    `list_foas` returns `eligibility_description` and no `eligibility` key, so
    reading only the latter left the column empty in every exported row.
    """

    def test_falls_back_to_the_description(self, tmp_path):
        path = tmp_path / "out.csv"
        export_foas_to_csv([_record(eligibility=None)], str(path))
        assert "Open to universities." in path.read_text(encoding="utf-8")

    def test_structured_list_still_wins(self, tmp_path):
        path = tmp_path / "out.csv"
        export_foas_to_csv(
            [_record(eligibility=["Universities", "Non-profits"])], str(path)
        )
        text = path.read_text(encoding="utf-8")
        assert "Universities;Non-profits" in text

    def test_no_eligibility_at_all_is_blank_not_the_string_none(self, tmp_path):
        path = tmp_path / "out.csv"
        export_foas_to_csv(
            [_record(eligibility=None, eligibility_description=None)], str(path)
        )
        assert "None" not in path.read_text(encoding="utf-8").split("\n")[1]


class TestJsonExport:
    def test_payload_shape(self):
        payload = build_export_payload([_record(), _record(foa_id="b", tags=[])])
        assert payload["record_count"] == 2
        assert payload["tagged_record_count"] == 1
        assert len(payload["foas"]) == 2

    def test_raw_payload_is_dropped_by_default(self):
        payload = build_export_payload([_record(raw_payload={"huge": "blob"})])
        assert "raw_payload" not in payload["foas"][0]

    def test_raw_payload_can_be_kept(self):
        payload = build_export_payload(
            [_record(raw_payload={"huge": "blob"})], include_raw_payload=True
        )
        assert payload["foas"][0]["raw_payload"] == {"huge": "blob"}

    def test_schema_version_falls_back_to_the_constant(self):
        """`list_foas` does not select the column; do not emit an empty list."""
        payload = build_export_payload([_record()])
        assert payload["schema_version"] == SCHEMA_VERSION

    def test_schema_version_taken_from_records_when_present(self):
        payload = build_export_payload([_record(schema_version="2.1")])
        assert payload["schema_version"] == "2.1"

    def test_mixed_schema_versions_are_surfaced(self):
        payload = build_export_payload(
            [_record(schema_version="1.0"), _record(foa_id="b", schema_version="2.0")]
        )
        assert payload["schema_version"] == ["1.0", "2.0"]

    def test_writes_a_file_and_round_trips(self, tmp_path):
        path = tmp_path / "out.json"
        export_foas_to_json([_record()], str(path))
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["record_count"] == 1
        assert loaded["foas"][0]["foa_id"] == "abc-123"

    def test_keeps_full_nested_tags_unlike_the_flattened_csv(self, tmp_path):
        path = tmp_path / "out.json"
        export_foas_to_json([_record()], str(path))
        tag = json.loads(path.read_text(encoding="utf-8"))["foas"][0]["tags"][0]
        assert tag["category"] == "research_discipline"
        assert tag["source_layer"] == "layer_1_terminological"

    def test_description_is_not_truncated(self, tmp_path):
        """The CSV truncates to 500 chars for Excel; JSON must not."""
        long_text = "x" * 2000
        path = tmp_path / "out.json"
        export_foas_to_json([_record(program_description=long_text)], str(path))
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert len(loaded["foas"][0]["program_description"]) == 2000

    def test_export_is_byte_stable_across_runs(self, tmp_path):
        """A diff should mean the data changed, not that the exporter ran."""
        a, b = tmp_path / "a.json", tmp_path / "b.json"
        export_foas_to_json([_record()], str(a))
        export_foas_to_json([_record()], str(b))
        assert a.read_bytes() == b.read_bytes()

    def test_returns_a_string_when_no_path_given(self):
        text = export_foas_to_json([_record()])
        assert json.loads(text)["record_count"] == 1

    def test_empty_dataset(self, tmp_path):
        path = tmp_path / "out.json"
        export_foas_to_json([], str(path))
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["record_count"] == 0
        assert loaded["foas"] == []
