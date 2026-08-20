"""Tests for LLM-generated match explanations (matching/explain.py)."""

import requests

from foa_pipeline.matching.explain import (
    MatchExplainer,
    _fallback_explanation,
    annotate_with_explanations,
)


def _foa(foa_id, hybrid_score=0.5, cosine_score=0.5, tag_overlap_ratio=0.0,
         matched_tags=None, **extra):
    d = {
        "foa_id": foa_id,
        "title": f"Programme {foa_id}",
        "program_description": "Studies things.",
        "hybrid_score": hybrid_score,
        "cosine_score": cosine_score,
        "tag_overlap_ratio": tag_overlap_ratio,
        "matched_tags": matched_tags or [],
    }
    d.update(extra)
    return d


class _Resp:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, json_body=None, raise_for_status_exc=None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self._raise_exc = raise_for_status_exc

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc


def _mock_model_available(monkeypatch, model="mistral:7b-instruct"):
    """is_available() will report True: /api/tags lists the configured model."""
    body = {"models": [{"name": model}]}
    monkeypatch.setattr(requests, "get", lambda url, timeout: _Resp(200, body))


def _mock_llm_response(monkeypatch, explanation="x", relevance="weak"):
    """Every /api/generate call returns the same canned explanation/relevance."""
    body = {"response": f'{{"explanation": "{explanation}", "relevance": "{relevance}"}}'}
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))


class TestFallbackExplanation:
    def test_mentions_matched_tags_when_present(self):
        foa = _foa(
            "a", tag_overlap_ratio=0.5, cosine_score=0.8,
            matched_tags=["Machine Learning", "Veterans"],
        )
        text = _fallback_explanation(foa)
        assert "Machine Learning" in text
        assert "Veterans" in text
        assert "50%" in text
        assert "80%" in text

    def test_cosine_only_when_no_matched_tags(self):
        foa = _foa("a", cosine_score=0.73, matched_tags=[])
        text = _fallback_explanation(foa)
        assert "73%" in text
        assert "Matches on" not in text

    def test_caps_at_four_tags(self):
        foa = _foa("a", matched_tags=["A", "B", "C", "D", "E", "F"])
        text = _fallback_explanation(foa)
        assert "E" not in text and "F" not in text


class TestMatchExplainerAvailability:
    def test_available_when_model_present(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get",
            lambda url, timeout: _Resp(200, {"models": [{"name": "mistral:7b-instruct"}]}),
        )
        explainer = MatchExplainer(model="mistral:7b-instruct")
        assert explainer.is_available() is True

    def test_unavailable_when_model_missing(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get",
            lambda url, timeout: _Resp(200, {"models": [{"name": "other-model"}]}),
        )
        explainer = MatchExplainer(model="mistral:7b-instruct")
        assert explainer.is_available() is False

    def test_unavailable_when_unreachable(self, monkeypatch):
        def raise_conn_error(url, timeout):
            raise requests.RequestException("connection refused")

        monkeypatch.setattr(requests, "get", raise_conn_error)
        assert MatchExplainer().is_available() is False


class TestMatchExplainerExplainOne:
    def test_parses_valid_response(self, monkeypatch):
        body = {"response": '{"explanation": "Strong topical fit.", "relevance": "strong"}'}
        monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))

        result = MatchExplainer().explain_one("profile", _foa("a"))
        assert result == {"explanation": "Strong topical fit.", "relevance": "strong"}

    def test_relevance_is_case_normalised(self, monkeypatch):
        body = {"response": '{"explanation": "Fits.", "relevance": "STRONG"}'}
        monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))

        result = MatchExplainer().explain_one("profile", _foa("a"))
        assert result["relevance"] == "strong"

    def test_unrecognised_relevance_value_becomes_none(self, monkeypatch):
        """Explanation prose survives even when the tier can't be parsed."""
        body = {"response": '{"explanation": "Fits okay.", "relevance": "somewhat"}'}
        monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))

        result = MatchExplainer().explain_one("profile", _foa("a"))
        assert result["explanation"] == "Fits okay."
        assert result["relevance"] is None

    def test_malformed_json_falls_back(self, monkeypatch):
        body = {"response": "not json at all"}
        monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))

        foa = _foa("a", cosine_score=0.6)
        result = MatchExplainer().explain_one("profile", foa)
        assert result["relevance"] is None
        assert "60%" in result["explanation"]  # the deterministic fallback sentence

    def test_empty_explanation_falls_back(self, monkeypatch):
        body = {"response": '{"explanation": "", "relevance": "strong"}'}
        monkeypatch.setattr(requests, "post", lambda url, json, timeout: _Resp(200, body))

        foa = _foa("a", cosine_score=0.4)
        result = MatchExplainer().explain_one("profile", foa)
        assert result["relevance"] is None
        assert "40%" in result["explanation"]

    def test_connection_error_falls_back(self, monkeypatch):
        def raise_conn_error(url, json, timeout):
            raise requests.ConnectionError("Ollama is down")

        monkeypatch.setattr(requests, "post", raise_conn_error)
        foa = _foa("a", cosine_score=0.9)
        result = MatchExplainer().explain_one("profile", foa)
        assert result["relevance"] is None
        assert "90%" in result["explanation"]

    def test_http_error_falls_back(self, monkeypatch):
        exc = requests.HTTPError("500 server error")
        monkeypatch.setattr(
            requests, "post",
            lambda url, json, timeout: _Resp(500, {}, raise_for_status_exc=exc),
        )

        result = MatchExplainer().explain_one("profile", _foa("a"))
        assert result["relevance"] is None
        assert isinstance(result["explanation"], str) and result["explanation"]

    def test_prompt_is_grounded_in_the_foa_and_profile(self, monkeypatch):
        """The prompt sent to the model must carry the actual scores, not placeholders."""
        captured = {}

        def fake_post(url, json, timeout):
            captured["prompt"] = json["prompt"]
            return _Resp(200, {"response": '{"explanation": "x", "relevance": "weak"}'})

        monkeypatch.setattr(requests, "post", fake_post)
        foa = _foa(
            "a", cosine_score=0.77, tag_overlap_ratio=0.33, matched_tags=["Climate Action"]
        )
        MatchExplainer().explain_one("housing policy researcher", foa)

        assert "housing policy researcher" in captured["prompt"]
        assert "Climate Action" in captured["prompt"]
        assert "0.77" in captured["prompt"]

    def test_caps_generation_length(self, monkeypatch):
        """The task is one sentence; an uncapped model can ramble, and this
        call runs sequentially up to 5x per match request, so any per-call
        slowness is paid for repeatedly. Measured ~19% faster with this cap."""
        captured = {}

        def fake_post(url, json, timeout):
            captured["options"] = json["options"]
            return _Resp(200, {"response": '{"explanation": "x", "relevance": "weak"}'})

        monkeypatch.setattr(requests, "post", fake_post)
        MatchExplainer().explain_one("profile", _foa("a"))

        assert captured["options"]["num_predict"] == 150


class TestAnnotateWithExplanations:
    def test_empty_input_returns_empty(self):
        result = annotate_with_explanations("profile", [], explainer=None, explain_top_k=5)
        assert result == {"items": [], "llm_available": False}

    def test_no_explainer_uses_fallback_on_window_only(self):
        foas = [_foa(str(i), cosine_score=0.5) for i in range(3)]
        result = annotate_with_explanations("profile", foas, explainer=None, explain_top_k=2)

        assert result["llm_available"] is False
        assert "match_explanation" in result["items"][0]
        assert "match_explanation" in result["items"][1]
        assert "match_explanation" not in result["items"][2]  # beyond the window

    def test_explain_top_k_zero_never_pings_ollama(self, monkeypatch):
        pinged = []
        monkeypatch.setattr(requests, "get", lambda *a, **k: pinged.append(1))

        foas = [_foa("a")]
        explainer = MatchExplainer()
        result = annotate_with_explanations("profile", foas, explainer, explain_top_k=0)

        assert pinged == []
        assert result["llm_available"] is False
        assert "match_explanation" not in result["items"][0]

    def test_unavailable_explainer_falls_back_for_whole_window(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda url, timeout: _Resp(200, {"models": []}))

        foas = [_foa("a", cosine_score=0.55)]
        result = annotate_with_explanations("profile", foas, MatchExplainer(), explain_top_k=5)

        assert result["llm_available"] is False
        assert "55%" in result["items"][0]["match_explanation"]

    def test_reorders_window_by_relevance_tier(self, monkeypatch):
        _mock_model_available(monkeypatch)

        # "weak" ranked highest by hybrid_score but should sort behind "strong".
        by_id = {
            "weak_but_top_score": "weak",
            "strong_but_low_score": "strong",
            "moderate_mid_score": "moderate",
        }

        def fake_post(url, json, timeout):
            for fid, tier in by_id.items():
                if fid in json["prompt"]:
                    body = {"response": f'{{"explanation": "x", "relevance": "{tier}"}}'}
                    return _Resp(200, body)
            raise AssertionError("unrecognised foa in prompt")

        monkeypatch.setattr(requests, "post", fake_post)

        foas = [
            _foa("weak_but_top_score", hybrid_score=0.9),
            _foa("strong_but_low_score", hybrid_score=0.1),
            _foa("moderate_mid_score", hybrid_score=0.5),
        ]
        result = annotate_with_explanations("profile", foas, MatchExplainer(), explain_top_k=3)

        assert [f["foa_id"] for f in result["items"]] == [
            "strong_but_low_score", "moderate_mid_score", "weak_but_top_score",
        ]
        assert result["llm_available"] is True

    def test_ties_within_a_tier_break_by_hybrid_score(self, monkeypatch):
        _mock_model_available(monkeypatch)
        _mock_llm_response(monkeypatch, relevance="strong")

        foas = [_foa("low", hybrid_score=0.3), _foa("high", hybrid_score=0.8)]
        result = annotate_with_explanations("profile", foas, MatchExplainer(), explain_top_k=2)

        assert [f["foa_id"] for f in result["items"]] == ["high", "low"]

    def test_items_beyond_window_keep_relative_order_and_position(self, monkeypatch):
        _mock_model_available(monkeypatch)
        _mock_llm_response(monkeypatch, relevance="weak")

        foas = [_foa(f"foa_{i}", hybrid_score=1.0 - i * 0.1) for i in range(5)]
        result = annotate_with_explanations("profile", foas, MatchExplainer(), explain_top_k=2)

        tail_ids = [f["foa_id"] for f in result["items"][2:]]
        assert tail_ids == ["foa_2", "foa_3", "foa_4"]
        assert "match_explanation" not in result["items"][2]

    def test_unscored_relevance_sorts_after_all_named_tiers(self, monkeypatch):
        """A response the LLM answered but couldn't be tiered still sorts last, not first."""
        _mock_model_available(monkeypatch)

        def fake_post(url, json, timeout):
            if "unparseable" in json["prompt"]:
                return _Resp(200, {"response": '{"explanation": "x", "relevance": "who knows"}'})
            return _Resp(200, {"response": '{"explanation": "x", "relevance": "weak"}'})

        monkeypatch.setattr(requests, "post", fake_post)

        foas = [_foa("unparseable", hybrid_score=0.99), _foa("weak_tier", hybrid_score=0.01)]
        result = annotate_with_explanations("profile", foas, MatchExplainer(), explain_top_k=2)

        assert [f["foa_id"] for f in result["items"]] == ["weak_tier", "unparseable"]
