"""
Tests for the silver-set annotator.

The property that matters most here is that a top-up run adds one category
without destroying the other four. The set was annotated before
`research_discipline` existed, so filling that gap means editing files that
already hold 249 labels — losing them would be silent and expensive.
"""

import json

import pytest

from foa_pipeline.evaluation import synthetic_annotator as sa


class TestCategoryAttribution:
    def test_every_prefix_maps_to_a_prompted_category(self):
        """A category we can detect but cannot prompt for would never fill."""
        for category in sa.PREFIX_TO_CATEGORY.values():
            assert category in sa.CATEGORY_PROMPTS

    def test_all_five_ontology_categories_are_covered(self):
        assert set(sa.CATEGORY_PROMPTS) == {
            "sponsor_theme", "research_domain", "method",
            "population", "research_discipline",
        }

    def test_category_of_known_prefixes(self):
        assert sa._category_of("nsf_bio") == "research_discipline"
        assert sa._category_of("great_01") == "sponsor_theme"
        assert sa._category_of("sdg_04") == "research_domain"
        assert sa._category_of("method_25") == "method"
        assert sa._category_of("pop_03") == "population"

    def test_category_of_unknown_is_none(self):
        assert sa._category_of("mystery_01") is None

    def test_category_of_tolerates_non_strings(self):
        """Tags come from a hand-editable JSON file."""
        assert sa._category_of(None) is None
        assert sa._category_of(42) is None

    def test_categories_present_detects_the_gap(self):
        """This is the exact state of eval_set_50.json before the top-up."""
        tags = ["great_01", "sdg_04", "method_02", "pop_03"]
        present = sa.categories_present(tags)
        assert "research_discipline" not in present
        assert len(present) == 4

    def test_categories_present_after_top_up(self):
        tags = ["great_01", "sdg_04", "method_02", "pop_03", "nsf_bio"]
        assert len(sa.categories_present(tags)) == 5

    def test_categories_present_on_empty(self):
        assert sa.categories_present([]) == set()


class TestProvenance:
    def test_records_source_model_and_time(self):
        record = sa._record_provenance(None, ["research_discipline"], "mistral")
        entry = record["research_discipline"]
        assert entry["source"] == "llm"
        assert entry["model"] == "mistral"
        assert "annotated_at" in entry

    def test_preserves_other_categories(self):
        prior = {"method": {"source": "llm", "model": "old", "annotated_at": "x"}}
        record = sa._record_provenance(prior, ["research_discipline"], "mistral")
        assert record["method"]["model"] == "old"
        assert record["research_discipline"]["model"] == "mistral"

    def test_overwrites_the_same_category(self):
        prior = {"method": {"source": "llm", "model": "old", "annotated_at": "x"}}
        record = sa._record_provenance(prior, ["method"], "new")
        assert record["method"]["model"] == "new"

    def test_does_not_mutate_the_input(self):
        prior = {"method": {"source": "llm", "model": "old", "annotated_at": "x"}}
        sa._record_provenance(prior, ["method"], "new")
        assert prior["method"]["model"] == "old"


class TestOllamaResponseParsing:
    """`call_ollama` must cope with the shapes a 7B model actually returns."""

    def _patch(self, monkeypatch, payload):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"response": json.dumps(payload)}

        monkeypatch.setattr(sa.requests, "post", lambda *a, **k: FakeResponse())

    def test_plain_list(self, monkeypatch):
        self._patch(monkeypatch, ["nsf_bio", "nsf_geo"])
        assert sa.call_ollama("u", "m", "p") == ["nsf_bio", "nsf_geo"]

    def test_ids_in_a_wrapper_list(self, monkeypatch):
        self._patch(monkeypatch, {"tags": ["nsf_bio"]})
        assert "nsf_bio" in sa.call_ollama("u", "m", "p")

    def test_ids_used_as_dict_keys(self, monkeypatch):
        """The failure mode that once made every annotation come back empty."""
        self._patch(monkeypatch, {"nsf_bio": ["biology", "cells"]})
        assert "nsf_bio" in sa.call_ollama("u", "m", "p")

    def test_malformed_json_returns_empty(self, monkeypatch):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"response": "not json at all"}

        monkeypatch.setattr(sa.requests, "post", lambda *a, **k: FakeResponse())
        assert sa.call_ollama("u", "m", "p", max_retries=0) == []

    def test_request_failure_returns_empty(self, monkeypatch):
        def boom(*a, **k):
            raise sa.requests.RequestException("down")

        monkeypatch.setattr(sa.requests, "post", boom)
        assert sa.call_ollama("u", "m", "p", max_retries=0) == []


class TestTopUpRun:
    """End-to-end over a fake Ollama and a temporary eval file."""

    def _setup(self, tmp_path, monkeypatch, responses, entries):
        eval_dir = tmp_path / "evaluation"
        eval_dir.mkdir()
        (eval_dir / "eval_set_50.json").write_text(json.dumps(entries), encoding="utf-8")

        class Cfg:
            evaluation_dir = eval_dir
            app_db_path = tmp_path / "app.db"
            ollama_base_url = "http://fake"
            ollama_model = "mistral"

        monkeypatch.setattr(sa, "get_config", lambda: Cfg())
        monkeypatch.setattr(sa, "Database", lambda path: object())
        monkeypatch.setattr(sa, "get_concepts_by_category", lambda db: {
            "research_discipline": [
                {"id": f"nsf_{x}", "label": x} for x in
                ("bio", "cise", "edu", "eng", "geo", "mps", "sbe", "tip")
            ],
            "method": [{"id": f"method_{i:02d}", "label": str(i)} for i in range(25)],
        })
        monkeypatch.setattr(sa, "call_ollama", lambda *a, **k: responses)
        return eval_dir / "eval_set_50.json"

    def _entry(self, tags):
        return {
            "foa_id": "abcdef123456",
            "title": "A study of cells",
            "program_description": "Research into cellular biology.",
            "human_tags": list(tags),
        }

    def test_adds_the_missing_category_and_keeps_the_rest(self, tmp_path, monkeypatch):
        existing = ["great_01", "sdg_04", "method_02", "pop_03"]
        path = self._setup(tmp_path, monkeypatch, ["nsf_bio"], [self._entry(existing)])

        sa.annotate_foas(categories=["research_discipline"])

        result = json.loads(path.read_text())[0]
        assert "nsf_bio" in result["human_tags"]
        for tag in existing:
            assert tag in result["human_tags"], f"lost pre-existing {tag}"
        assert len(result["human_tags"]) == 5

    def test_records_provenance_only_for_the_requested_category(self, tmp_path, monkeypatch):
        path = self._setup(tmp_path, monkeypatch, ["nsf_bio"], [self._entry(["method_02"])])
        sa.annotate_foas(categories=["research_discipline"])
        prov = json.loads(path.read_text())[0]["annotation_provenance"]
        assert set(prov) == {"research_discipline"}
        assert prov["research_discipline"]["source"] == "llm"

    def test_skips_foas_that_already_have_the_category(self, tmp_path, monkeypatch):
        path = self._setup(
            tmp_path, monkeypatch, ["nsf_geo"], [self._entry(["method_02", "nsf_bio"])]
        )
        stats = sa.annotate_foas(categories=["research_discipline"])
        result = json.loads(path.read_text())[0]
        assert stats["annotated"] == 0
        assert "nsf_geo" not in result["human_tags"]
        assert "nsf_bio" in result["human_tags"]

    def test_overwrite_replaces_only_that_category(self, tmp_path, monkeypatch):
        path = self._setup(
            tmp_path, monkeypatch, ["nsf_geo"], [self._entry(["method_02", "nsf_bio"])]
        )
        sa.annotate_foas(categories=["research_discipline"], overwrite=True)
        tags = json.loads(path.read_text())[0]["human_tags"]
        assert "nsf_geo" in tags
        assert "nsf_bio" not in tags
        assert "method_02" in tags

    def test_full_list_echo_is_discarded(self, tmp_path, monkeypatch):
        """A model returning every directorate is not making a judgement."""
        everything = ["nsf_bio", "nsf_cise", "nsf_edu", "nsf_eng",
                      "nsf_geo", "nsf_mps", "nsf_sbe", "nsf_tip"]
        path = self._setup(tmp_path, monkeypatch, everything, [self._entry(["method_02"])])
        sa.annotate_foas(categories=["research_discipline"])
        tags = json.loads(path.read_text())[0]["human_tags"]
        assert not any(t.startswith("nsf_") for t in tags)

    def test_invalid_ids_are_dropped(self, tmp_path, monkeypatch):
        path = self._setup(
            tmp_path, monkeypatch, ["nsf_bio", "nsf_wizardry"], [self._entry([])]
        )
        sa.annotate_foas(categories=["research_discipline"])
        assert json.loads(path.read_text())[0]["human_tags"] == ["nsf_bio"]

    def test_untagged_foa_with_no_text_keeps_its_labels(self, tmp_path, monkeypatch):
        entry = {"foa_id": "abcdef123456", "title": "", "human_tags": ["method_02"]}
        path = self._setup(tmp_path, monkeypatch, ["nsf_bio"], [entry])
        sa.annotate_foas(categories=["research_discipline"])
        assert json.loads(path.read_text())[0]["human_tags"] == ["method_02"]

    def test_unknown_category_is_rejected(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, [], [self._entry([])])
        with pytest.raises(ValueError, match="No prompt defined"):
            sa.annotate_foas(categories=["not_a_category"])
