"""
Tests for the OpenAlex harvester and the NSF crosswalk.

The property guarded hardest here is that the vendored CSV stays *inert*.
Registering a sixth category while no evaluation set carries a single OpenAlex
label would make every prediction in it a false positive and collapse global
gold F1 — the same failure the silver set had with `research_discipline`.
"""

from pathlib import Path

import pytest

from foa_pipeline.ingestion.openalex import (
    OPENALEX_CATEGORY,
    VENDORED_FILENAME,
    build_domain_rows,
    build_field_rows,
    domain_concept_id,
    field_concept_id,
    load_vendored_fields,
    parse_synonyms,
    write_ontology_csv,
)
from foa_pipeline.ontology.openalex_crosswalk import (
    NSF_TO_OPENALEX,
    UNMAPPED_OPENALEX_FIELDS,
    WEAK_MAPPINGS,
    coverage_report,
    directorates_for,
    is_weak,
    openalex_fields_for,
    primary_openalex_field,
)

ONTOLOGY_DIR = Path("data/ontology")

NSF_DIRECTORATES = {
    "nsf_bio", "nsf_cise", "nsf_edu", "nsf_eng",
    "nsf_geo", "nsf_mps", "nsf_sbe", "nsf_tip",
}


def _api_field(fid, name, domain_id=3, domain="Physical Sciences", alts=None, desc="d"):
    return {
        "id": f"https://openalex.org/fields/{fid}",
        "display_name": name,
        "description": desc,
        "display_name_alternatives": alts if alts is not None else [],
        "domain": {"id": f"https://openalex.org/domains/{domain_id}",
                   "display_name": domain},
    }


class TestIdDerivation:
    def test_field_id_from_url(self):
        assert field_concept_id("https://openalex.org/fields/22") == "oa_field_22"

    def test_domain_id_from_url(self):
        assert domain_concept_id("https://openalex.org/domains/3") == "oa_domain_3"

    def test_trailing_slash_is_tolerated(self):
        assert field_concept_id("https://openalex.org/fields/22/") == "oa_field_22"


class TestRowBuilding:
    def test_builds_a_field_row(self):
        rows = build_field_rows([_api_field(22, "Engineering", alts=["engineering sciences"])])
        assert rows == [{
            "concept_id": "oa_field_22",
            "label": "Engineering",
            "category": OPENALEX_CATEGORY,
            "parent_id": "oa_domain_3",
            "description": "d",
            "synonyms": "engineering sciences",
        }]

    def test_multiple_synonyms_are_pipe_separated(self):
        """Commas are unusable: field names contain them."""
        rows = build_field_rows([_api_field(20, "Economics, Econometrics and Finance",
                                            alts=["economics", "finance"])])
        assert rows[0]["synonyms"] == "economics|finance"
        assert parse_synonyms(rows[0]["synonyms"]) == ["economics", "finance"]

    def test_field_without_alternatives(self):
        rows = build_field_rows([_api_field(26, "Mathematics", alts=[])])
        assert rows[0]["synonyms"] == ""
        assert parse_synonyms(rows[0]["synonyms"]) == []

    def test_entity_without_id_is_skipped(self):
        assert build_field_rows([{"display_name": "Nameless"}]) == []

    def test_domains_are_deduplicated(self):
        fields = [
            _api_field(22, "Engineering", 3, "Physical Sciences"),
            _api_field(16, "Chemistry", 3, "Physical Sciences"),
            _api_field(33, "Social Sciences", 2, "Social Sciences"),
        ]
        domains = build_domain_rows(fields)
        assert [d["concept_id"] for d in domains] == ["oa_domain_2", "oa_domain_3"]

    def test_rows_are_ordered_stably(self):
        """A re-harvest must produce an empty diff unless OpenAlex changed."""
        fields = [_api_field(31, "Physics"), _api_field(11, "Bio"), _api_field(22, "Eng")]
        first = build_field_rows(fields)
        second = build_field_rows(list(reversed(fields)))
        assert first == second

    def test_parse_synonyms_handles_missing(self):
        assert parse_synonyms(None) == []
        assert parse_synonyms("") == []
        assert parse_synonyms(" | ") == []


class TestCsvRoundTrip:
    def test_written_csv_reads_back(self, tmp_path):
        rows = build_field_rows([_api_field(22, "Engineering", alts=["a", "b"])])
        write_ontology_csv(rows, tmp_path / VENDORED_FILENAME)
        assert load_vendored_fields(tmp_path) == rows

    def test_missing_file_names_the_command(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="harvest-openalex"):
            load_vendored_fields(tmp_path)


class TestVendoredFileStaysInert:
    def test_not_registered_with_the_ontology_loader(self):
        """
        The loader uses an explicit filename whitelist. If this test fails,
        someone registered the file and global gold F1 will collapse, because
        no eval set carries an OpenAlex label.
        """
        import inspect

        from foa_pipeline.ontology.store import OntologyStore

        source = inspect.getsource(OntologyStore.load_all_ontologies)
        assert VENDORED_FILENAME not in source, (
            "openalex_fields.csv is now loaded into the live ontology. Do not "
            "enable it until an eval set carries OpenAlex labels."
        )

    def test_vendored_file_uses_its_own_category(self):
        """It must not collide with research_discipline, which stays the headline."""
        rows = load_vendored_fields(ONTOLOGY_DIR)
        assert {r["category"] for r in rows} == {OPENALEX_CATEGORY}
        assert OPENALEX_CATEGORY != "research_discipline"


class TestVendoredContent:
    @pytest.fixture
    def rows(self):
        return load_vendored_fields(ONTOLOGY_DIR)

    def test_has_26_fields_and_4_domains(self):
        rows = load_vendored_fields(ONTOLOGY_DIR)
        fields = [r for r in rows if r["concept_id"].startswith("oa_field_")]
        domains = [r for r in rows if r["concept_id"].startswith("oa_domain_")]
        assert len(fields) == 26
        assert len(domains) == 4

    def test_every_field_has_a_description(self, rows):
        """The reason for adopting this taxonomy; assert it holds."""
        for row in rows:
            if row["concept_id"].startswith("oa_field_"):
                assert row["description"], f"{row['label']} has no description"

    def test_every_field_has_a_real_parent(self, rows):
        """Activates the hierarchy machinery that is currently dormant."""
        domain_ids = {r["concept_id"] for r in rows if r["concept_id"].startswith("oa_domain_")}
        for row in rows:
            if row["concept_id"].startswith("oa_field_"):
                assert row["parent_id"] in domain_ids

    def test_most_fields_carry_synonyms(self, rows):
        with_syn = sum(
            1 for r in rows
            if r["concept_id"].startswith("oa_field_") and parse_synonyms(r["synonyms"])
        )
        assert with_syn >= 20


class TestCrosswalk:
    def test_covers_every_nsf_directorate(self):
        assert set(NSF_TO_OPENALEX) == NSF_DIRECTORATES

    def test_targets_exist_in_the_vendored_file(self):
        valid = {r["concept_id"] for r in load_vendored_fields(ONTOLOGY_DIR)}
        for directorate, fields in NSF_TO_OPENALEX.items():
            for field in fields:
                assert field in valid, f"{directorate} -> unknown field {field}"

    def test_unmapped_fields_are_really_unmapped(self):
        """Guards the documented NSF/NIH coverage gap against silent drift."""
        mapped = {f for fields in NSF_TO_OPENALEX.values() for f in fields}
        assert mapped & UNMAPPED_OPENALEX_FIELDS == set()

    def test_health_sciences_have_no_nsf_directorate(self):
        for field in ("oa_field_27", "oa_field_29", "oa_field_35"):
            assert directorates_for(field) == []

    def test_primary_field_is_the_first_listed(self):
        assert primary_openalex_field("nsf_cise") == "oa_field_17"
        assert primary_openalex_field("nsf_eng") == "oa_field_22"

    def test_unknown_directorate_returns_nothing(self):
        assert openalex_fields_for("nsf_wizardry") == []
        assert primary_openalex_field("nsf_wizardry") is None

    def test_reverse_lookup_finds_shared_fields(self):
        """Social Sciences receives both SBE and STEM Education."""
        assert directorates_for("oa_field_33") == ["nsf_edu", "nsf_sbe"]

    def test_materials_science_is_shared_by_eng_and_mps(self):
        assert directorates_for("oa_field_25") == ["nsf_eng", "nsf_mps"]

    def test_weak_mappings_are_flagged(self):
        assert is_weak("nsf_tip")
        assert not is_weak("nsf_bio")
        assert WEAK_MAPPINGS <= NSF_DIRECTORATES

    def test_coverage_report(self):
        report = coverage_report()
        assert report["directorates"] == 8
        assert report["openalex_fields_unmapped"] == len(UNMAPPED_OPENALEX_FIELDS)
        assert "oa_field_33" in report["fields_shared_by_multiple_directorates"]
