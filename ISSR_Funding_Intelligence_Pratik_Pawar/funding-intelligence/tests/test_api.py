"""Tests for the FastAPI layer (routes, dependency wiring, validation)."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from foa_pipeline.api import deps
from foa_pipeline.api.app import create_app
from foa_pipeline.storage.database import Database


@pytest.fixture
def api_db_path(tmp_path, sample_foa):
    """Path to a populated temp database.

    Returns a path rather than a live connection: TestClient dispatches sync
    routes on a worker thread, and SQLite forbids using a connection from a
    thread other than the one that created it.
    """
    db_path = tmp_path / "api_test.db"
    db = Database(db_path)

    open_foa = copy.deepcopy(sample_foa)
    open_foa["foa_id"] = "api-foa-open"
    open_foa["source_id"] = "open-1"
    open_foa["title"] = "Rural Health Machine Learning Initiative"
    open_foa["status"] = "open"
    db.upsert_foa(open_foa)

    closed_foa = copy.deepcopy(sample_foa)
    closed_foa["foa_id"] = "api-foa-closed"
    closed_foa["source_id"] = "closed-1"
    closed_foa["title"] = "Archived Coastal Erosion Study"
    closed_foa["status"] = "closed"
    closed_foa["agency"] = "Department of Energy"
    db.upsert_foa(closed_foa)

    db.save_tags(
        "api-foa-open",
        [
            {
                "tag_id": "layer_1_terminological:method_01",
                "label": "Machine Learning",
                "category": "method",
                "source_layer": "layer_1_terminological",
                "confidence": 1.0,
                "context_snippet": "machine learning approaches",
                "ontology_concept_id": "method_01",
            },
            {
                "tag_id": "layer_2_embedding:pop_01",
                "label": "Rural Communities",
                "category": "population",
                "source_layer": "layer_2_embedding",
                "confidence": 0.62,
                "context_snippet": "rural communities",
                "ontology_concept_id": "pop_01",
            },
        ],
    )

    db.close()
    return db_path


@pytest.fixture
def client(api_db_path):
    """TestClient with the DB dependency pointed at the temp database."""
    app = create_app()

    def override_get_db():
        db = Database(api_db_path)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealth:
    def test_health_reports_stats(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "healthy"
        assert body["total_foas"] == 2
        assert body["open_foas"] == 1
        assert body["total_tags"] == 2


class TestOpportunities:
    def test_list_returns_paginated_envelope(self, client):
        body = client.get("/api/opportunities").json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert len(body["items"]) == 2

    def test_list_filters_by_status(self, client):
        body = client.get("/api/opportunities", params={"status": "open"}).json()
        assert body["total"] == 1
        assert body["items"][0]["foa_id"] == "api-foa-open"

    def test_list_respects_page_size(self, client):
        body = client.get("/api/opportunities", params={"size": 1}).json()
        assert len(body["items"]) == 1
        assert body["total"] == 2

    def test_get_single_opportunity(self, client):
        body = client.get("/api/opportunities/api-foa-open").json()
        assert body["foa_id"] == "api-foa-open"
        assert body["title"] == "Rural Health Machine Learning Initiative"

    def test_unknown_opportunity_returns_404(self, client):
        assert client.get("/api/opportunities/does-not-exist").status_code == 404

    def test_raw_payload_is_never_exposed(self, client):
        """raw_payload is bulky source data and must be stripped from responses."""
        assert "raw_payload" not in client.get("/api/opportunities/api-foa-open").json()
        for item in client.get("/api/opportunities").json()["items"]:
            assert "raw_payload" not in item

    def test_recent_endpoint_is_not_shadowed_by_id_route(self, client):
        """/recent must resolve to the recent handler, not /{foa_id}."""
        resp = client.get("/api/opportunities/recent")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_rejects_invalid_pagination(self, client):
        assert client.get("/api/opportunities", params={"page": 0}).status_code == 422
        assert client.get("/api/opportunities", params={"size": 0}).status_code == 422

    def test_facets_endpoint_is_not_shadowed_by_id_route(self, client):
        """/facets must resolve to the facets handler, not /{foa_id} -> 404."""
        resp = client.get("/api/opportunities/facets")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "agency" in body

    def test_facets_report_both_seeded_statuses(self, client):
        body = client.get("/api/opportunities/facets").json()
        values = {row["value"]: row["count"] for row in body["status"]}
        assert values == {"open": 1, "closed": 1}

    def test_facets_narrow_with_the_same_filters_as_the_list_endpoint(self, client):
        """?status=open here must mean exactly what it means on the list endpoint."""
        body = client.get("/api/opportunities/facets", params={"status": "open"}).json()
        # agency is a DIFFERENT dimension from the one just filtered on, so it
        # should reflect only the one open record -- both seeded FOAs share
        # agency_code "NSF", so this also proves the filter narrowed at all.
        values = {row["value"]: row["count"] for row in body["agency"]}
        assert values == {"NSF": 1}


class TestKeywordSearch:
    def test_finds_matching_record(self, client):
        body = client.post("/api/search/keyword", json={"query": "rural"}).json()
        assert body["total"] >= 1
        assert any("Rural" in i["title"] for i in body["items"])

    def test_returns_empty_for_no_match(self, client):
        body = client.post(
            "/api/search/keyword", json={"query": "zzzznonexistentterm"}
        ).json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_echoes_query_and_pagination(self, client):
        body = client.post(
            "/api/search/keyword", json={"query": "rural", "page": 1, "size": 5}
        ).json()
        assert body["query"] == "rural"
        assert body["size"] == 5

    def test_rejects_empty_query(self, client):
        assert client.post("/api/search/keyword", json={"query": ""}).status_code == 422

    def test_rejects_missing_query(self, client):
        assert client.post("/api/search/keyword", json={}).status_code == 422

    def test_strips_raw_payload(self, client):
        body = client.post("/api/search/keyword", json={"query": "rural"}).json()
        for item in body["items"]:
            assert "raw_payload" not in item


class TestSemanticSearch:
    def test_reports_missing_index_gracefully(self, client, tmp_path, monkeypatch):
        """With no FAISS index built, the endpoint explains rather than erroring."""
        from foa_pipeline.api.routes import search as search_route
        from foa_pipeline.matching.vector_index import VectorIndex

        empty_index = VectorIndex(
            db=None, model_name="unused", cache_dir=tmp_path / "no-index"
        )
        # Patch the name bound inside the route module, not deps: the route
        # imported it directly, so patching deps would have no effect.
        monkeypatch.setattr(search_route, "get_vector_index", lambda: empty_index)

        resp = client.post(
            "/api/search/semantic",
            json={"profile_text": "machine learning for rural health"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert "FAISS index not found" in body["message"]

    def test_rejects_too_short_profile(self, client):
        resp = client.post("/api/search/semantic", json={"profile_text": "short"})
        assert resp.status_code == 422

    def test_rejects_out_of_range_k(self, client):
        resp = client.post(
            "/api/search/semantic",
            json={"profile_text": "a sufficiently long research profile", "k": 0},
        )
        assert resp.status_code == 422


class FakeVectorIndex:
    """Stand-in for VectorIndex returning canned FAISS hits, shaped like real
    search() output: full FOA fields plus an injected similarity_score."""

    def __init__(self, results):
        self.index = True  # truthy: route treats this as "index loaded"
        self._results = results

    def search(self, query, k=10, threshold=0.0, db=None):
        self.last_threshold = threshold
        self.last_db = db
        return [dict(r) for r in self._results]


class FakeExplainer:
    """Stand-in for MatchExplainer with a scripted availability and answer."""

    def __init__(self, available=True, relevance="strong"):
        self._available = available
        self._relevance = relevance
        self.calls = []

    def is_available(self):
        return self._available

    def explain_one(self, profile_text, foa):
        self.calls.append(foa["foa_id"])
        return {
            "explanation": f"Fake explanation for {foa['foa_id']}.",
            "relevance": self._relevance,
        }


class TestMatch:
    """/api/match: hybrid ranking, optionally annotated with LLM explanations."""

    PROFILE = "machine learning for rural health"

    def _index(self):
        return FakeVectorIndex([
            {
                "foa_id": "api-foa-open",
                "title": "Rural Health Machine Learning Initiative",
                "status": "open",
                "program_description": "Studies rural health using machine learning.",
                "similarity_score": 0.81,
            },
            {
                "foa_id": "api-foa-closed",
                "title": "Archived Coastal Erosion Study",
                "status": "closed",
                "program_description": "Coastal erosion research.",
                "similarity_score": 0.40,
            },
        ])

    def _patch(self, monkeypatch, index=None, tagger=None, explainer=None):
        from foa_pipeline.api.routes import match as match_route

        monkeypatch.setattr(match_route, "get_vector_index", lambda: index or self._index())
        monkeypatch.setattr(match_route, "get_tagger_pipeline", lambda: tagger)
        monkeypatch.setattr(
            match_route, "get_match_explainer", lambda: explainer or FakeExplainer()
        )

    def test_reports_missing_index_gracefully(self, client, tmp_path, monkeypatch):
        from foa_pipeline.api.routes import match as match_route
        from foa_pipeline.matching.vector_index import VectorIndex

        empty_index = VectorIndex(db=None, model_name="unused", cache_dir=tmp_path / "no-index")
        monkeypatch.setattr(match_route, "get_vector_index", lambda: empty_index)

        resp = client.post("/api/match", json={"profile_text": self.PROFILE})
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["llm_available"] is False
        assert "FAISS index not found" in body["message"]

    def test_rejects_too_short_profile(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post("/api/match", json={"profile_text": "short"})
        assert resp.status_code == 422

    def test_rejects_out_of_range_k(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post("/api/match", json={"profile_text": self.PROFILE, "k": 0})
        assert resp.status_code == 422

    def test_status_filter_applied_after_ranking(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "status": "open", "explain": False},
        )
        body = resp.json()
        assert [i["foa_id"] for i in body["items"]] == ["api-foa-open"]

    def test_forwards_the_request_scoped_db_to_vector_search(self, client, monkeypatch):
        """
        The cached VectorIndex holds no Database of its own (api/deps.py) --
        a real request 500s if match_profile_to_foas does not forward its db
        argument into vector_index.search(). Caught only by exercising the
        real route end-to-end, not by matcher.py's unit tests alone, since
        those construct match_profile_to_foas' inputs directly.
        """
        index = self._index()
        self._patch(monkeypatch, index=index)

        resp = client.post("/api/match", json={"profile_text": self.PROFILE, "explain": False})
        assert resp.status_code == 200
        assert index.last_db is not None

    def test_explain_false_skips_llm_entirely(self, client, monkeypatch):
        explainer = FakeExplainer()
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "status": None, "explain": False},
        )
        body = resp.json()
        assert body["llm_available"] is False
        assert explainer.calls == []
        assert all("match_explanation" not in item for item in body["items"])

    def test_explain_true_annotates_top_results(self, client, monkeypatch):
        explainer = FakeExplainer(available=True, relevance="strong")
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "status": None, "explain": True},
        )
        body = resp.json()
        assert body["llm_available"] is True
        items = body["items"]
        assert all(item["match_explanation"].startswith("Fake explanation") for item in items)
        assert all(item["llm_relevance"] == "strong" for item in items)

    def test_explainer_unavailable_degrades_without_error(self, client, monkeypatch):
        explainer = FakeExplainer(available=False)
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "status": None, "explain": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["llm_available"] is False
        assert explainer.calls == []
        # Still gets a deterministic explanation, just not an LLM-authored one.
        assert all("match_explanation" in item for item in body["items"])

    def test_without_tagger_falls_back_to_cosine_only_ranking(self, client, monkeypatch):
        self._patch(monkeypatch, tagger=None)
        resp = client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "status": None, "explain": False},
        )
        body = resp.json()
        assert all(item["tag_overlap_ratio"] == 0.0 for item in body["items"])

    def test_raw_payload_is_never_exposed(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post(
            "/api/match", json={"profile_text": self.PROFILE, "explain": False}
        )
        for item in resp.json()["items"]:
            assert "raw_payload" not in item

    def test_threshold_is_passed_through_to_the_vector_search(self, client, monkeypatch):
        index = self._index()
        self._patch(monkeypatch, index=index)

        client.post(
            "/api/match",
            json={"profile_text": self.PROFILE, "threshold": 0.42, "explain": False},
        )
        assert index.last_threshold == 0.42

    def test_no_results_reports_empty_not_an_error(self, client, monkeypatch):
        self._patch(monkeypatch, index=FakeVectorIndex([]))
        resp = client.post(
            "/api/match", json={"profile_text": "a sufficiently long research profile"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0


class TestMatchStream:
    """
    /api/match/stream: same ranking/explanation as /api/match, delivered as
    newline-delimited JSON. Deliberately not a TestMatch subclass -- pytest
    would rediscover and rerun every inherited test method against this
    class too, redundantly re-testing the atomic endpoint under a class
    named for the streaming one. _index/_patch/PROFILE are duplicated from
    TestMatch instead, small enough that the duplication is cheaper than
    that footgun.
    """

    PROFILE = "machine learning for rural health"

    def _index(self):
        return FakeVectorIndex([
            {
                "foa_id": "api-foa-open",
                "title": "Rural Health Machine Learning Initiative",
                "status": "open",
                "program_description": "Studies rural health using machine learning.",
                "similarity_score": 0.81,
            },
            {
                "foa_id": "api-foa-closed",
                "title": "Archived Coastal Erosion Study",
                "status": "closed",
                "program_description": "Coastal erosion research.",
                "similarity_score": 0.40,
            },
        ])

    def _patch(self, monkeypatch, index=None, tagger=None, explainer=None):
        from foa_pipeline.api.routes import match as match_route

        monkeypatch.setattr(match_route, "get_vector_index", lambda: index or self._index())
        monkeypatch.setattr(match_route, "get_tagger_pipeline", lambda: tagger)
        monkeypatch.setattr(
            match_route, "get_match_explainer", lambda: explainer or FakeExplainer()
        )

    def _events(self, resp):
        return [json.loads(line) for line in resp.text.strip().split("\n") if line]

    def test_missing_index_reports_gracefully(self, client, tmp_path, monkeypatch):
        from foa_pipeline.api.routes import match as match_route
        from foa_pipeline.matching.vector_index import VectorIndex

        empty_index = VectorIndex(db=None, model_name="unused", cache_dir=tmp_path / "no-index")
        monkeypatch.setattr(match_route, "get_vector_index", lambda: empty_index)

        resp = client.post("/api/match/stream", json={"profile_text": self.PROFILE})
        assert resp.status_code == 200
        events = self._events(resp)
        assert events[0]["type"] == "ranked"
        assert events[0]["items"] == []
        assert "FAISS index not found" in events[0]["message"]
        assert events[-1] == {"type": "done", "llm_available": False}

    def test_ranked_event_arrives_first_with_all_items(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": None, "explain": False},
        )
        events = self._events(resp)
        assert events[0]["type"] == "ranked"
        assert {i["foa_id"] for i in events[0]["items"]} == {"api-foa-open", "api-foa-closed"}

    def test_explain_window_size_is_zero_when_explain_is_false(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": None, "explain": False},
        )
        events = self._events(resp)
        assert events[0]["explain_window_size"] == 0

    def test_explain_false_skips_llm_and_streams_no_explanation_events(self, client, monkeypatch):
        explainer = FakeExplainer()
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": None, "explain": False},
        )
        events = self._events(resp)
        assert explainer.calls == []
        assert [e["type"] for e in events] == ["ranked", "done"]
        assert events[-1]["llm_available"] is False

    def test_explain_true_streams_one_explanation_event_per_item_then_reorders(
        self, client, monkeypatch
    ):
        explainer = FakeExplainer(available=True, relevance="strong")
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": None, "explain": True},
        )
        events = self._events(resp)
        types = [e["type"] for e in events]
        assert types == ["ranked", "explanation", "explanation", "reorder", "done"]
        # Both fixture items fit under top_k, so a client should expect an
        # "explanation" event for each of them.
        assert events[0]["explain_window_size"] == 2

        explanation_events = [e for e in events if e["type"] == "explanation"]
        assert {e["foa_id"] for e in explanation_events} == {"api-foa-open", "api-foa-closed"}
        assert all(e["llm_relevance"] == "strong" for e in explanation_events)
        assert all(
            e["match_explanation"].startswith("Fake explanation") for e in explanation_events
        )

        reorder = events[-2]
        assert set(reorder["foa_ids"]) == {"api-foa-open", "api-foa-closed"}
        assert events[-1] == {"type": "done", "llm_available": True}

    def test_explainer_unavailable_degrades_without_reorder_event(self, client, monkeypatch):
        explainer = FakeExplainer(available=False)
        self._patch(monkeypatch, explainer=explainer)

        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": None, "explain": True},
        )
        events = self._events(resp)
        assert explainer.calls == []
        # Still gets deterministic fallback explanations, just no LLM-ordered
        # reorder event -- the atomic endpoint's window keeps hybrid order.
        assert [e["type"] for e in events] == ["ranked", "explanation", "explanation", "done"]
        assert events[-1]["llm_available"] is False

    def test_status_filter_applied_before_streaming_starts(self, client, monkeypatch):
        self._patch(monkeypatch)
        resp = client.post(
            "/api/match/stream",
            json={"profile_text": self.PROFILE, "status": "open", "explain": False},
        )
        events = self._events(resp)
        assert [i["foa_id"] for i in events[0]["items"]] == ["api-foa-open"]

    def test_matches_the_atomic_endpoint_s_final_content(self, client, monkeypatch):
        """The two endpoints should agree on substance -- same ranking, same
        explanations, same final order -- differing only in delivery shape."""
        self._patch(monkeypatch, explainer=FakeExplainer(available=True, relevance="moderate"))
        atomic = client.post(
            "/api/match", json={"profile_text": self.PROFILE, "status": None, "explain": True}
        ).json()

        self._patch(monkeypatch, explainer=FakeExplainer(available=True, relevance="moderate"))
        events = self._events(
            client.post(
                "/api/match/stream",
                json={"profile_text": self.PROFILE, "status": None, "explain": True},
            )
        )
        reorder = next(e for e in events if e["type"] == "reorder")
        assert reorder["foa_ids"] == [i["foa_id"] for i in atomic["items"]]


class TestTags:
    def test_list_tags(self, client):
        body = client.get("/api/tags").json()
        assert body["total"] == 2
        labels = {t["label"] for t in body["tags"]}
        assert {"Machine Learning", "Rural Communities"} <= labels

    def test_filter_tags_by_category(self, client):
        body = client.get("/api/tags", params={"category": "method"}).json()
        assert body["total"] == 1
        assert body["tags"][0]["category"] == "method"

    def test_categories_aggregate_counts(self, client):
        cats = {c["category"]: c for c in client.get("/api/tags/categories").json()["categories"]}
        assert cats["method"]["concept_count"] == 1
        assert cats["population"]["concept_count"] == 1

    def test_tag_detail_lists_tagged_foas(self, client):
        body = client.get("/api/tags/method_01").json()
        assert body["concept_id"] == "method_01"
        assert body["total"] == 1
        assert body["foas"][0]["foa_id"] == "api-foa-open"

    def test_unknown_concept_returns_empty_not_error(self, client):
        body = client.get("/api/tags/nonexistent_concept").json()
        assert body["total"] == 0
        assert body["foas"] == []


class TestExport:
    def test_csv_export_has_header_and_rows(self, client):
        resp = client.get("/api/export/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        lines = [ln for ln in resp.text.splitlines() if ln.strip()]
        assert len(lines) >= 3  # header + 2 records
        assert "foa_id" in lines[0]

    def test_json_export_returns_records(self, client):
        body = client.get("/api/export/json").json()
        assert body["total"] == 2
        assert len(body["foas"]) == 2

    def test_json_export_strips_raw_payload(self, client):
        for record in client.get("/api/export/json").json()["foas"]:
            assert "raw_payload" not in record

    def test_export_respects_status_filter(self, client):
        resp = client.get("/api/export/csv", params={"status": "open"})
        lines = [ln for ln in resp.text.splitlines() if ln.strip()]
        assert len(lines) == 2  # header + 1 open record


class TestExportBounds:
    def test_reports_totals_and_no_truncation_for_small_sets(self, client):
        resp = client.get("/api/export/csv")
        assert resp.headers["x-total-count"] == "2"
        assert resp.headers["x-returned-count"] == "2"
        assert "x-export-truncated" not in resp.headers

    def test_flags_truncation_when_page_is_smaller_than_total(self, client):
        resp = client.get("/api/export/csv", params={"size": 1})
        assert resp.headers["x-total-count"] == "2"
        assert resp.headers["x-returned-count"] == "1"
        assert resp.headers["x-export-truncated"] == "true"
        assert resp.headers["x-next-page"] == "2"

    def test_json_export_reports_truncation(self, client):
        body = client.get("/api/export/json", params={"size": 1}).json()
        assert body["total"] == 2
        assert body["returned"] == 1
        assert body["truncated"] is True

    def test_export_paging_returns_different_records(self, client):
        first = client.get("/api/export/json", params={"size": 1, "page": 1}).json()
        second = client.get("/api/export/json", params={"size": 1, "page": 2}).json()
        assert first["foas"][0]["foa_id"] != second["foas"][0]["foa_id"]

    def test_size_is_capped_by_configured_maximum(self, client, monkeypatch):
        """A caller cannot request an unbounded export."""
        from foa_pipeline.api.routes import export as export_route

        cfg = deps.get_app_config()
        capped = cfg.__class__(**{**cfg.__dict__, "api_export_max_rows": 1})
        monkeypatch.setattr(export_route, "get_app_config", lambda: capped)

        body = client.get("/api/export/json", params={"size": 999999}).json()
        assert body["returned"] == 1
        assert body["size"] == 1


class TestRateLimiting:
    def test_requests_under_limit_are_allowed(self, api_db_path):
        app = create_app()

        def override_get_db():
            db = Database(api_db_path)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[deps.get_db] = override_get_db
        with TestClient(app) as c:
            for _ in range(5):
                assert c.get("/api/opportunities").status_code == 200

    def test_exceeding_limit_returns_429_with_retry_after(self, api_db_path, monkeypatch):
        from foa_pipeline.api import app as app_module

        cfg = deps.get_app_config()
        strict = cfg.__class__(**{**cfg.__dict__, "api_rate_limit_per_minute": 3})
        monkeypatch.setattr(app_module, "get_app_config", lambda: strict)

        app = app_module.create_app()

        def override_get_db():
            db = Database(api_db_path)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[deps.get_db] = override_get_db

        with TestClient(app) as c:
            statuses = [c.get("/api/opportunities").status_code for _ in range(5)]

        assert statuses[:3] == [200, 200, 200]
        assert 429 in statuses[3:]

    def test_health_endpoint_is_exempt_from_limiting(self, api_db_path, monkeypatch):
        """Uptime checks must not be throttled out."""
        from foa_pipeline.api import app as app_module

        cfg = deps.get_app_config()
        strict = cfg.__class__(**{**cfg.__dict__, "api_rate_limit_per_minute": 2})
        monkeypatch.setattr(app_module, "get_app_config", lambda: strict)

        app = app_module.create_app()

        def override_get_db():
            db = Database(api_db_path)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[deps.get_db] = override_get_db

        with TestClient(app) as c:
            statuses = [c.get("/api/health").status_code for _ in range(6)]

        assert all(s == 200 for s in statuses)


class TestCors:
    def test_configured_origin_is_allowed(self, client):
        resp = client.get(
            "/api/health", headers={"Origin": "http://localhost:8000"}
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_unlisted_origin_is_not_echoed_back(self, client):
        """The API previously allowed any origin with credentials enabled."""
        resp = client.get("/api/health", headers={"Origin": "http://evil.example.com"})
        assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"
        assert resp.headers.get("access-control-allow-origin") != "*"


class TestAppWiring:
    def test_openapi_schema_documents_all_route_groups(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        for expected in [
            "/api/health",
            "/api/opportunities",
            "/api/opportunities/{foa_id}",
            "/api/search/keyword",
            "/api/search/semantic",
            "/api/tags",
            "/api/export/csv",
        ]:
            assert expected in paths, f"{expected} missing from OpenAPI schema"

    def test_vector_index_is_cached_across_calls(self):
        """The FAISS index must not be rebuilt per request (was ~3.3s each)."""
        deps.get_vector_index.cache_clear()
        try:
            assert deps.get_vector_index() is deps.get_vector_index()
        finally:
            deps.get_vector_index.cache_clear()
