"""Tests for the database module."""

import copy
import sqlite3
import threading

from foa_pipeline.storage.database import Database


def test_upsert_and_get(tmp_path, sample_foa):
    """Test inserting and retrieving a FOA record."""
    db = Database(tmp_path / "test.db")

    is_new = db.upsert_foa(sample_foa)
    assert is_new is True

    # Retrieve
    record = db.get_foa(sample_foa["foa_id"])
    assert record is not None
    assert record["title"] == sample_foa["title"]
    assert record["agency_code"] == "NSF"
    assert "47.075" in record["cfda_numbers"]
    assert "Universities" in record["eligibility"]

    # Update (same foa_id)
    sample_foa["title"] = "Updated Title"
    is_new = db.upsert_foa(sample_foa)
    assert is_new is False

    updated = db.get_foa(sample_foa["foa_id"])
    assert updated["title"] == "Updated Title"

    db.close()


def test_list_with_filters(tmp_path, sample_foa):
    """Test listing FOAs with filters."""
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    # List all
    records, total = db.list_foas()
    assert total == 1
    assert len(records) == 1

    # Filter by status
    records, total = db.list_foas(status="open")
    assert total == 1

    records, total = db.list_foas(status="closed")
    assert total == 0

    # Filter by agency
    records, total = db.list_foas(agency_code="NSF")
    assert total == 1

    records, total = db.list_foas(agency_code="NIH")
    assert total == 0

    db.close()


def test_fts_search(tmp_path, sample_foa):
    """Test full-text search."""
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    # Search by keyword in title
    records, total = db.search_fts("climate")
    assert total >= 1

    # Search by keyword in description
    records, total = db.search_fts("rural communities")
    assert total >= 1

    # No results
    records, total = db.search_fts("quantum computing")
    assert total == 0


def test_fts_search_survives_pathological_input(tmp_path, sample_foa):
    """
    Unsanitized, a lone '-' or an unmatched '"' reaches FTS5's query parser
    as operator syntax and raises sqlite3.OperationalError -- this is now the
    app's primary search bar, so it must not 500 on ordinary typing.
    """
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    records, total = db.search_fts("-")
    assert total == 0

    records, total = db.search_fts('"unterminated')
    assert total == 0

    # A quote-containing query that legitimately matches should still work.
    records, total = db.search_fts('"climate change"')
    assert total >= 1

    db.close()


def test_fts_search_parses_funding_tiers(tmp_path, sample_foa):
    """
    list_foas() already parses funding_tiers from its stored JSON string;
    search_fts() silently didn't -- callers reading this field off a search
    result got a raw JSON string instead of a list.
    """
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    records, _ = db.search_fts("climate")
    assert isinstance(records[0]["funding_tiers"], list)

    db.close()


def test_facet_counts_reflect_the_corpus(tmp_path, sample_foa):
    db = Database(tmp_path / "test.db")

    open_nsf = copy.deepcopy(sample_foa)
    db.upsert_foa(open_nsf)

    closed_nih = copy.deepcopy(sample_foa)
    closed_nih["foa_id"] = "test-uuid-002"
    closed_nih["source_id"] = "654321"
    closed_nih["status"] = "closed"
    closed_nih["agency_code"] = "NIH"
    db.upsert_foa(closed_nih)

    facets = db.get_facet_counts()

    assert {"value": "open", "count": 1} in facets["status"]
    assert {"value": "closed", "count": 1} in facets["status"]
    assert {"value": "NSF", "count": 1} in facets["agency_code"]
    assert {"value": "NIH", "count": 1} in facets["agency_code"]

    db.close()


def test_facet_counts_exclude_their_own_dimension(tmp_path, sample_foa):
    """
    Facet counts reflect every OTHER active filter, not the one they're
    counting toward. Filtering to a single agency must not make every other
    agency option read zero -- that would defeat the point of a sidebar
    that's supposed to let a user switch agencies, not just confirm one.
    """
    db = Database(tmp_path / "test.db")

    nsf = copy.deepcopy(sample_foa)
    db.upsert_foa(nsf)

    nih = copy.deepcopy(sample_foa)
    nih["foa_id"] = "test-uuid-002"
    nih["source_id"] = "654321"
    nih["agency_code"] = "NIH"
    db.upsert_foa(nih)

    # Filtered to NSF: the agency facet must still show NIH's real count.
    facets = db.get_facet_counts(agency_code="NSF")
    assert {"value": "NIH", "count": 1} in facets["agency_code"]
    assert {"value": "NSF", "count": 1} in facets["agency_code"]

    # But status, a DIFFERENT dimension, DOES respect the agency filter --
    # only NSF's one "open" record should be counted, not NIH's.
    assert facets["status"] == [{"value": "open", "count": 1}]

    db.close()


def test_facet_counts_omit_nulls(tmp_path, sample_foa):
    """A record with no agency_code should not produce a {"value": null} bucket."""
    db = Database(tmp_path / "test.db")

    no_agency = copy.deepcopy(sample_foa)
    no_agency["agency_code"] = None
    db.upsert_foa(no_agency)

    facets = db.get_facet_counts()
    assert facets["agency_code"] == []

    db.close()

    db.close()


def test_tag_operations(tmp_path, sample_foa):
    """Test saving and retrieving tags."""
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    tags = [
        {
            "concept_id": "sdg_13",
            "label": "Climate Action",
            "category": "research_domain",
            "source_layer": "layer_1_terminological",
            "confidence": 1.0,
            "context_snippet": "climate change impacts on rural communities",
        },
        {
            "concept_id": "pop_01",
            "label": "Rural Communities",
            "category": "population",
            "source_layer": "layer_1_terminological",
            "confidence": 1.0,
            "context_snippet": "rural communities",
        },
    ]

    count = db.save_tags(sample_foa["foa_id"], tags)
    assert count == 2

    # Retrieve tags
    retrieved = db.get_tags_for_foa(sample_foa["foa_id"])
    assert len(retrieved) == 2
    labels = {t["label"] for t in retrieved}
    assert "Climate Action" in labels
    assert "Rural Communities" in labels

    # Get FOAs by tag
    records, total = db.get_foas_by_tag("sdg_13")
    assert total == 1

    db.close()


def test_stats(tmp_path, sample_foa):
    """Test summary statistics."""
    db = Database(tmp_path / "test.db")
    db.upsert_foa(sample_foa)

    stats = db.get_stats()
    assert stats["total_foas"] == 1
    assert stats["open_foas"] == 1
    assert stats["total_tags"] == 0

    db.close()


class TestCrossThreadUsage:
    """
    Reproduces the exact failure the API's get_db() dependency hit once the
    Next.js frontend started issuing concurrent Server Component fetches
    (Promise.all): a request succeeded (200, real data returned) and still
    500'd, because Starlette's BaseHTTPMiddleware ran the sync get_db()
    generator's `yield` and its `finally: db.close()` on different threadpool
    workers within that one request's lifecycle. Default sqlite3 behaviour
    raises on that even though no two requests ever touched the connection
    concurrently -- it isn't the cross-request race the check exists to
    catch, just Starlette's own thread-hop inside a single request.
    """

    def test_default_rejects_use_from_another_thread(self, tmp_path, sample_foa):
        """Confirms the failure mode is real, not a misdiagnosis."""
        db = Database(tmp_path / "test.db")
        db.upsert_foa(sample_foa)

        errors = []

        def close_from_other_thread():
            try:
                db.close()
            except sqlite3.ProgrammingError as exc:
                errors.append(exc)

        t = threading.Thread(target=close_from_other_thread)
        t.start()
        t.join()

        assert len(errors) == 1
        assert "different thread" in str(errors[0]) or "same thread" in str(errors[0])

    def test_check_same_thread_false_permits_close_from_another_thread(self, tmp_path, sample_foa):
        """The actual fix: get_db() opens with check_same_thread=False."""
        db = Database(tmp_path / "test.db", check_same_thread=False)
        db.upsert_foa(sample_foa)

        errors = []

        def use_and_close_from_other_thread():
            try:
                record = db.get_foa(sample_foa["foa_id"])
                assert record is not None
                db.close()
            except sqlite3.ProgrammingError as exc:
                errors.append(exc)

        t = threading.Thread(target=use_and_close_from_other_thread)
        t.start()
        t.join()

        assert errors == []

    def test_default_construction_is_unaffected(self, tmp_path):
        """
        CLI commands and evaluation scripts construct Database() with no
        arguments and are genuinely single-threaded -- confirms the new
        parameter is opt-in (defaults to the prior, safer behaviour) and
        ordinary same-thread usage isn't disturbed by adding it.
        """
        db = Database(tmp_path / "test.db")
        try:
            assert db.conn.execute("PRAGMA schema_version").fetchone() is not None
        finally:
            db.close()
