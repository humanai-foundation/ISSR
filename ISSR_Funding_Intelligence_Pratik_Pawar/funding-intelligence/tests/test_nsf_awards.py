"""
Tests for the NSF award connector.

The crosswalks here encode empirical facts about a live API, so the tests guard
the two failure modes that would silently corrupt the evaluation corpus:
mislabelling an award, and labelling one that has no valid label at all.
"""

import pytest

from foa_pipeline.ingestion.nsf_awards import (
    CFDA_TO_CONCEPT,
    DIRECTORATE_ABBR_TO_CONCEPT,
    HARVEST_CFDA_NUMBERS,
    acceptable_concepts,
    build_award_record,
    directorate_to_concept,
    parse_cfda_numbers,
)

# The eight research directorates in data/ontology/nsf_directorates.csv.
ONTOLOGY_CONCEPTS = {
    "nsf_bio", "nsf_cise", "nsf_edu", "nsf_eng",
    "nsf_geo", "nsf_mps", "nsf_sbe", "nsf_tip",
}


class TestCrosswalkIntegrity:
    """Every concept produced must exist in the ontology."""

    def test_abbreviation_crosswalk_targets_are_real_concepts(self):
        for abbr, concept in DIRECTORATE_ABBR_TO_CONCEPT.items():
            if concept is not None:
                assert concept in ONTOLOGY_CONCEPTS, f"{abbr} -> unknown concept {concept}"

    def test_cfda_crosswalk_targets_are_real_concepts(self):
        for number, concept in CFDA_TO_CONCEPT.items():
            if concept is not None:
                assert concept in ONTOLOGY_CONCEPTS, f"{number} -> unknown concept {concept}"

    def test_harvest_partitions_are_all_labelled(self):
        """Harvesting an unlabelled CFDA would spend requests on unusable data."""
        for number in HARVEST_CFDA_NUMBERS:
            assert CFDA_TO_CONCEPT.get(number) is not None

    def test_harvest_partitions_cover_every_directorate(self):
        covered = {CFDA_TO_CONCEPT[n] for n in HARVEST_CFDA_NUMBERS}
        assert covered == ONTOLOGY_CONCEPTS

    def test_cise_abbreviation_is_cse_not_cise(self):
        """The API's abbreviation disagrees with the concept ID; regression guard."""
        assert directorate_to_concept("CSE") == "nsf_cise"

    def test_office_of_the_director_is_not_a_discipline(self):
        assert directorate_to_concept("O/D") is None


class TestDirectorateMapping:
    def test_known_abbreviations(self):
        assert directorate_to_concept("BIO") == "nsf_bio"
        assert directorate_to_concept("MPS") == "nsf_mps"
        assert directorate_to_concept("TIP") == "nsf_tip"

    def test_abbreviation_is_case_and_space_insensitive(self):
        assert directorate_to_concept(" bio ") == "nsf_bio"

    def test_renamed_directorate_maps_to_current_concept(self):
        """EHR was renamed EDU in 2023; historical awards must not be lost."""
        assert directorate_to_concept("EHR") == "nsf_edu"
        assert directorate_to_concept("EDU") == "nsf_edu"

    def test_falls_back_to_long_name_when_abbreviation_missing(self):
        assert directorate_to_concept(
            None, "Directorate for Geosciences"
        ) == "nsf_geo"

    def test_long_name_match_ignores_case_and_whitespace(self):
        assert directorate_to_concept(
            None, "  Directorate  for   Engineering  "
        ) == "nsf_eng"

    def test_unknown_inputs_return_none_rather_than_guessing(self):
        assert directorate_to_concept("XYZ") is None
        assert directorate_to_concept(None, "Directorate for Wizardry") is None
        assert directorate_to_concept(None, None) is None
        assert directorate_to_concept("", "") is None

    def test_unknown_abbreviation_still_tries_the_long_name(self):
        assert directorate_to_concept("ZZZ", "Directorate for Biological Sciences") == "nsf_bio"


class TestCfdaParsing:
    def test_single_number(self):
        assert parse_cfda_numbers("47.074") == ["47.074"]

    def test_co_funded_award_yields_every_number(self):
        assert parse_cfda_numbers("47.041, 47.070") == ["47.041", "47.070"]

    def test_whitespace_variants(self):
        assert parse_cfda_numbers(" 47.041 ,47.070 ") == ["47.041", "47.070"]

    def test_empty_and_missing(self):
        assert parse_cfda_numbers(None) == []
        assert parse_cfda_numbers("") == []
        assert parse_cfda_numbers(" , ") == []


class TestAcceptableConcepts:
    def test_solo_award_accepts_only_its_directorate(self):
        assert acceptable_concepts("nsf_bio", ["47.074"]) == ["nsf_bio"]

    def test_co_funded_award_accepts_both_directorates(self):
        result = acceptable_concepts("nsf_eng", ["47.041", "47.070"])
        assert result == ["nsf_eng", "nsf_cise"]

    def test_primary_is_always_first(self):
        """Strict scoring reads element 0, so its position is part of the contract."""
        result = acceptable_concepts("nsf_geo", ["47.070", "47.050"])
        assert result[0] == "nsf_geo"

    def test_unlabelled_cfda_numbers_are_dropped(self):
        assert acceptable_concepts("nsf_sbe", ["47.075", "47.083"]) == ["nsf_sbe"]

    def test_no_duplicates_when_cfda_agrees_with_directorate(self):
        assert acceptable_concepts("nsf_mps", ["47.049", "47.049"]) == ["nsf_mps"]

    def test_no_primary_still_returns_cofunders(self):
        assert acceptable_concepts(None, ["47.049"]) == ["nsf_mps"]


class TestBuildAwardRecord:
    def _award(self, **overrides):
        award = {
            "id": "2349311",
            "title": "REU Site: Microbial Biofilms",
            "abstractText": "This REU Site award will support ten students.",
            "dirAbbr": "BIO",
            "orgLongName": "Directorate for Biological Sciences",
            "orgLongName2": "Division of Biological Infrastructure",
            "cfdaNumber": "47.074",
            "fundProgramName": "RSCH EXPER FOR UNDERGRAD SITES",
            "date": "03/28/2024",
        }
        award.update(overrides)
        return award

    def test_builds_a_labelled_record(self):
        record = build_award_record(self._award())
        assert record is not None
        assert record["award_id"] == "2349311"
        assert record["primary_concept_id"] == "nsf_bio"
        assert record["acceptable_concept_ids"] == ["nsf_bio"]
        assert record["division_name"] == "Division of Biological Infrastructure"
        assert record["source"] == "nsf_awards"

    def test_abstract_is_stripped(self):
        record = build_award_record(self._award(abstractText="  text  "))
        assert record["abstract"] == "text"

    def test_award_without_abstract_is_rejected(self):
        """No text means nothing to classify."""
        assert build_award_record(self._award(abstractText="")) is None
        assert build_award_record(self._award(abstractText="   ")) is None
        award = self._award()
        del award["abstractText"]
        assert build_award_record(award) is None

    def test_award_without_id_is_rejected(self):
        assert build_award_record(self._award(id="")) is None

    def test_award_from_a_non_research_office_is_rejected(self):
        """O/D awards have no discipline; inventing one would fabricate truth."""
        assert build_award_record(
            self._award(dirAbbr="O/D", orgLongName="Office Of The Director")
        ) is None

    def test_award_with_unmappable_directorate_is_rejected(self):
        assert build_award_record(
            self._award(dirAbbr="ZZZ", orgLongName="Directorate for Wizardry")
        ) is None

    def test_co_funded_award_records_all_cfda_numbers(self):
        record = build_award_record(
            self._award(dirAbbr="ENG",
                        orgLongName="Directorate for Engineering",
                        cfdaNumber="47.041, 47.070")
        )
        assert record["cfda_numbers"] == ["47.041", "47.070"]
        assert record["acceptable_concept_ids"] == ["nsf_eng", "nsf_cise"]

    def test_missing_optional_fields_do_not_crash(self):
        award = {
            "id": "1",
            "abstractText": "Some research.",
            "dirAbbr": "MPS",
        }
        record = build_award_record(award)
        assert record is not None
        assert record["title"] == ""
        assert record["cfda_numbers"] == []
        assert record["division_name"] is None


class TestPagination:
    """`iter_awards` must respect the service's ceilings without live calls."""

    def _client(self, pages):
        from foa_pipeline.ingestion.nsf_awards import NSFAwardsClient

        client = NSFAwardsClient.__new__(NSFAwardsClient)
        client.calls = []

        def fake_get(params):
            client.calls.append(params)
            index = len(client.calls) - 1
            return {"response": {"award": pages[index] if index < len(pages) else []}}

        client._get = fake_get
        return client

    def test_stops_on_a_short_page(self):
        client = self._client([[{"id": str(i)} for i in range(10)]])
        awards = client.iter_awards("01/01/2024", "12/31/2024", rate_limit=0)
        assert len(awards) == 10
        assert len(client.calls) == 1

    def test_pages_until_exhausted(self):
        pages = [[{"id": str(i)} for i in range(25)], [{"id": "x"}]]
        client = self._client(pages)
        awards = client.iter_awards("01/01/2024", "12/31/2024", rate_limit=0)
        assert len(awards) == 26
        assert client.calls[0]["offset"] == 1
        assert client.calls[1]["offset"] == 26

    def test_stops_at_max_results(self):
        pages = [[{"id": str(i)} for i in range(25)] for _ in range(10)]
        client = self._client(pages)
        awards = client.iter_awards("01/01/2024", "12/31/2024", max_results=30, rate_limit=0)
        assert len(awards) == 30

    def test_clamps_to_the_services_query_ceiling(self):
        pages = [[{"id": f"{p}-{i}"} for i in range(25)] for p in range(200)]
        client = self._client(pages)
        awards = client.iter_awards(
            "01/01/2024", "12/31/2024", max_results=99999, rate_limit=0
        )
        assert len(awards) == 3000

    def test_empty_first_page_returns_nothing(self):
        client = self._client([[]])
        assert client.iter_awards("01/01/2024", "12/31/2024", rate_limit=0) == []

    def test_cfda_filter_is_passed_through(self):
        client = self._client([[{"id": "1"}]])
        client.iter_awards("01/01/2024", "12/31/2024", cfda_number="47.074", rate_limit=0)
        assert client.calls[0]["cfdaNumber"] == "47.074"

    def test_cfda_filter_omitted_when_not_requested(self):
        client = self._client([[{"id": "1"}]])
        client.iter_awards("01/01/2024", "12/31/2024", rate_limit=0)
        assert "cfdaNumber" not in client.calls[0]

    def test_page_size_never_exceeds_the_service_limit(self):
        client = self._client([[{"id": "1"}]])
        client.iter_awards("01/01/2024", "12/31/2024", rate_limit=0)
        assert client.calls[0]["rpp"] == 25


class TestHarvestIsolation:
    def test_harvest_writes_to_the_evaluation_directory(self, tmp_path, monkeypatch):
        """
        Awards must never land in the FOA corpus.

        This is the one property of this module that, if broken, corrupts the
        production database rather than just an experiment.
        """
        from foa_pipeline.ingestion import nsf_awards

        class FakeClient:
            def __init__(self, config):
                pass

            def iter_awards(self, **kwargs):
                cfda = kwargs.get("cfda_number")
                if cfda != "47.074":
                    return []
                return [{
                    "id": "1", "title": "T", "abstractText": "Body text.",
                    "dirAbbr": "BIO", "orgLongName": "Directorate for Biological Sciences",
                    "cfdaNumber": "47.074",
                }]

        monkeypatch.setattr(nsf_awards, "NSFAwardsClient", FakeClient)

        class Cfg:
            evaluation_dir = tmp_path / "evaluation"
            user_agent = "test"

        result = nsf_awards.harvest_awards(Cfg(), cfda_numbers=("47.074",), rate_limit=0)

        assert result["records_written"] == 1
        assert result["per_concept"] == {"nsf_bio": 1}
        assert (tmp_path / "evaluation" / "nsf_awards.jsonl").exists()
        assert not (tmp_path / "foa_records.db").exists()

    def test_rerunning_a_harvest_does_not_duplicate(self, tmp_path, monkeypatch):
        from foa_pipeline.ingestion import nsf_awards

        class FakeClient:
            def __init__(self, config):
                pass

            def iter_awards(self, **kwargs):
                return [{
                    "id": "1", "title": "T", "abstractText": "Body text.",
                    "dirAbbr": "BIO", "cfdaNumber": "47.074",
                }]

        monkeypatch.setattr(nsf_awards, "NSFAwardsClient", FakeClient)

        class Cfg:
            evaluation_dir = tmp_path / "evaluation"
            user_agent = "test"

        first = nsf_awards.harvest_awards(Cfg(), cfda_numbers=("47.074",), rate_limit=0)
        second = nsf_awards.harvest_awards(Cfg(), cfda_numbers=("47.074",), rate_limit=0)

        assert first["records_written"] == 1
        assert second["records_written"] == 0
        assert second["skipped_duplicate"] == 1

    def test_unlabelled_awards_are_counted_not_written(self, tmp_path, monkeypatch):
        from foa_pipeline.ingestion import nsf_awards

        class FakeClient:
            def __init__(self, config):
                pass

            def iter_awards(self, **kwargs):
                return [
                    {"id": "1", "abstractText": "Text.", "dirAbbr": "O/D"},
                    {"id": "2", "abstractText": "", "dirAbbr": "BIO"},
                ]

        monkeypatch.setattr(nsf_awards, "NSFAwardsClient", FakeClient)

        class Cfg:
            evaluation_dir = tmp_path / "evaluation"
            user_agent = "test"

        result = nsf_awards.harvest_awards(Cfg(), cfda_numbers=("47.074",), rate_limit=0)
        assert result["records_written"] == 0
        assert result["skipped_unlabelled"] == 2


@pytest.mark.network
class TestLiveApiContract:
    """
    Guards the assumptions this module encodes about a third-party API.

    Deselected by default (`-m "not network"`); run deliberately to check
    whether NSF has changed the response shape.
    """

    def test_response_shape_and_labels(self):
        import requests

        response = requests.get(
            "https://api.nsf.gov/services/v1/awards.json",
            params={"dateStart": "01/01/2024", "dateEnd": "12/31/2024",
                    "cfdaNumber": "47.074", "rpp": 5, "offset": 1},
            timeout=45,
        )
        response.raise_for_status()
        awards = response.json()["response"]["award"]

        assert awards, "API returned no awards"
        for award in awards:
            assert "abstractText" in award
            assert "dirAbbr" in award
            assert "orgLongName" in award

        solo = [a for a in awards if a.get("cfdaNumber", "").strip() == "47.074"]
        for award in solo:
            assert directorate_to_concept(award["dirAbbr"]) == "nsf_bio"
