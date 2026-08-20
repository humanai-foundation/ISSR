"""Tests for the LLM classification backstop (Layer 5).

Mirrors test_synthetic_annotator.py's mocking pattern -- the response
shapes a 7B model actually returns are the same failure modes in both
places, since both prompt it the same way.
"""

import json

import pytest

from foa_pipeline.ontology.store import OntologyStore
from foa_pipeline.tagging import layer5_llm_classify as l5


@pytest.fixture(scope="module")
def small_store(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l5_ontology")
    csv_path = tmp / "concepts.csv"
    csv_path.write_text(
        "concept_id,label,category,parent_id,description\n"
        "nsf_bio,Biological Sciences,research_discipline,,Biology and life sciences\n"
        "nsf_cise,Computer Science,research_discipline,,Computing and information science\n"
        "nsf_eng,Engineering,research_discipline,,Engineering research\n"
        "nsf_geo,Geosciences,research_discipline,,Earth and geosciences\n"
        "great_02,Health,sponsor_theme,,Biomedical and public health research\n"
    )
    store = OntologyStore(tmp / "test.db")
    store.load_from_csv(csv_path, "test")
    return store


class TestIsAvailable:
    def test_true_when_model_present(self, monkeypatch):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"models": [{"name": "mistral:7b-instruct"}]}

        monkeypatch.setattr(l5.requests, "get", lambda *a, **k: FakeResponse())
        clf = l5.LLMClassifier(model="mistral:7b-instruct")
        assert clf.is_available() is True

    def test_false_when_unreachable(self, monkeypatch):
        def boom(*a, **k):
            raise l5.requests.RequestException("down")

        monkeypatch.setattr(l5.requests, "get", boom)
        clf = l5.LLMClassifier()
        assert clf.is_available() is False

    def test_false_when_model_missing(self, monkeypatch):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"models": [{"name": "llama3"}]}

        monkeypatch.setattr(l5.requests, "get", lambda *a, **k: FakeResponse())
        clf = l5.LLMClassifier(model="mistral:7b-instruct")
        assert clf.is_available() is False


class TestCallOllamaResponseParsing:
    def _patch(self, monkeypatch, payload):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"response": json.dumps(payload)}

        monkeypatch.setattr(l5.requests, "post", lambda *a, **k: FakeResponse())

    def test_plain_list(self, monkeypatch):
        self._patch(monkeypatch, ["nsf_bio", "nsf_eng"])
        clf = l5.LLMClassifier()
        assert clf._call_ollama("p") == ["nsf_bio", "nsf_eng"]

    def test_ids_used_as_dict_keys(self, monkeypatch):
        self._patch(monkeypatch, {"nsf_bio": ["biology"]})
        clf = l5.LLMClassifier()
        assert "nsf_bio" in clf._call_ollama("p")

    def test_malformed_json_returns_empty(self, monkeypatch):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"response": "not json"}

        monkeypatch.setattr(l5.requests, "post", lambda *a, **k: FakeResponse())
        clf = l5.LLMClassifier()
        assert clf._call_ollama("p", max_retries=0) == []

    def test_request_failure_returns_empty(self, monkeypatch):
        def boom(*a, **k):
            raise Exception("down")

        monkeypatch.setattr(l5.requests, "post", boom)
        clf = l5.LLMClassifier()
        assert clf._call_ollama("p", max_retries=0) == []


class TestClassify:
    def test_empty_text_returns_no_evidence(self, small_store):
        clf = l5.LLMClassifier()
        assert clf.classify("", small_store) == []

    def test_valid_response_produces_tag_evidence(self, monkeypatch, small_store):
        monkeypatch.setattr(l5.LLMClassifier, "_call_ollama", lambda self, prompt, max_retries=2: (
            ["nsf_bio"] if "Directorate" in prompt else []
        ))
        clf = l5.LLMClassifier()
        evidence = clf.classify("Some biology-adjacent grant text.", small_store)
        assert len(evidence) == 1
        assert evidence[0].concept_id == "nsf_bio"
        assert evidence[0].source_layer == "layer_5_llm_classify"
        assert evidence[0].confidence == 0.75

    def test_invalid_concept_ids_are_dropped(self, monkeypatch, small_store):
        monkeypatch.setattr(
            l5.LLMClassifier, "_call_ollama",
            lambda self, prompt, max_retries=2: ["nsf_bio", "nsf_wizardry"],
        )
        clf = l5.LLMClassifier()
        evidence = clf.classify("text", small_store)
        ids = {e.concept_id for e in evidence}
        assert "nsf_wizardry" not in ids

    def test_full_list_echo_is_discarded(self, monkeypatch, small_store):
        """A model returning every directorate is not making a judgement."""
        # small_store's research_discipline category has 4 concepts, meeting
        # the >=4 guard threshold; 3/4 (75%) trips the >50% discard rule.
        monkeypatch.setattr(
            l5.LLMClassifier, "_call_ollama",
            lambda self, prompt, max_retries=2: (
                ["nsf_bio", "nsf_cise", "nsf_eng"] if "Directorate" in prompt else []
            ),
        )
        clf = l5.LLMClassifier()
        evidence = clf.classify("generic text", small_store)
        assert not any(e.category == "research_discipline" for e in evidence)

    def test_below_guard_threshold_is_kept(self, monkeypatch, small_store):
        """A 2/4 (50%) response does not trip the >50% discard rule."""
        monkeypatch.setattr(
            l5.LLMClassifier, "_call_ollama",
            lambda self, prompt, max_retries=2: (
                ["nsf_bio", "nsf_cise"] if "Directorate" in prompt else []
            ),
        )
        clf = l5.LLMClassifier()
        evidence = clf.classify("generic text", small_store)
        ids = {e.concept_id for e in evidence}
        assert {"nsf_bio", "nsf_cise"} <= ids

    def test_per_category_cap_applied(self, monkeypatch, small_store):
        monkeypatch.setattr(
            l5.LLMClassifier, "_call_ollama",
            lambda self, prompt, max_retries=2: (
                ["nsf_bio", "nsf_cise"] if "Directorate" in prompt else []
            ),
        )
        monkeypatch.setattr(l5, "MAX_CONCEPTS_PER_CATEGORY", 1)
        clf = l5.LLMClassifier()
        evidence = clf.classify("generic text", small_store)
        research_discipline_tags = [e for e in evidence if e.category == "research_discipline"]
        assert len(research_discipline_tags) <= 1

    def test_no_concepts_returned_is_fine(self, monkeypatch, small_store):
        monkeypatch.setattr(
            l5.LLMClassifier, "_call_ollama", lambda self, prompt, max_retries=2: []
        )
        clf = l5.LLMClassifier()
        assert clf.classify("text with no matches", small_store) == []
