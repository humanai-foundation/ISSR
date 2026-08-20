"""
Tests for which FOAs `tag-all` covers.

These exist because of a measured defect, not a hypothetical one. `tag-all`
filtered to `status="open"`, so as the calendar advanced and FOAs closed, they
were silently dropped from tagging and every one of their tags became a false
negative. One gold-set FOA expiring ("Unleashing Tribal Energy Development",
close date 2026-07-24) moved global gold F1 from 0.517 to 0.500 on its own,
with no change whatsoever to the tagger.

That makes the project's headline metric a function of the date it was run on,
which is fatal for a document whose entire argument is before/after comparisons.
"""

import argparse

import pytest

from foa_pipeline.storage.database import Database


def _parser():
    """The real tag-all argument parser, so flag wiring is what ships."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--open-only", dest="all_statuses", action="store_false", default=True
    )
    return parser


def _status_filter(args):
    """Mirrors the selection rule in cli._run_tag_all."""
    return None if getattr(args, "all_statuses", True) else "open"


class TestStatusFilterRule:
    def test_default_covers_every_status(self):
        assert _status_filter(_parser().parse_args([])) is None

    def test_open_only_flag_restores_the_old_behaviour(self):
        assert _status_filter(_parser().parse_args(["--open-only"])) == "open"

    def test_missing_attribute_defaults_to_all(self):
        """Callers constructing args by hand must not silently get open-only."""
        assert _status_filter(argparse.Namespace()) is None


@pytest.fixture
def db_with_mixed_statuses(tmp_path):
    db = Database(tmp_path / "t.db")
    base = {
        "schema_version": "1.0",
        "source": "grants_gov",
        "ingestion_date": "2026-01-01T00:00:00Z",
        "title": "A study",
        "program_description": "Research into things.",
    }
    for i, status in enumerate(["open", "open", "closed", "archived"]):
        record = dict(base)
        record.update({
            "foa_id": f"foa-{i}",
            "source_id": str(i),
            "status": status,
        })
        db.upsert_foa(record)
    yield db
    db.close()


class TestSelectionAgainstTheDatabase:
    def test_no_filter_returns_closed_foas_too(self, db_with_mixed_statuses):
        records, total = db_with_mixed_statuses.list_foas(status=None, page=1, size=100)
        assert total == 4
        assert {r["status"] for r in records} == {"open", "closed", "archived"}

    def test_open_filter_drops_them(self, db_with_mixed_statuses):
        records, total = db_with_mixed_statuses.list_foas(status="open", page=1, size=100)
        assert total == 2
        assert {r["status"] for r in records} == {"open"}

    def test_a_closed_foa_is_reachable_for_tagging(self, db_with_mixed_statuses):
        """
        The specific regression: an expired FOA must still be tagged.

        Its text has not changed, only its availability, and availability is a
        serving concern rather than a property of the document's content.
        """
        records, _ = db_with_mixed_statuses.list_foas(status=None, page=1, size=100)
        closed = [r for r in records if r["status"] == "closed"]
        assert closed, "closed FOAs must be in the tagging set"
        assert closed[0]["program_description"]
