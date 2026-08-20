"""Tests for the NSF funding-search listing scraper.

The dedup logic is the part that matters most here -- normalize_title and
is_likely_duplicate's 0.85 threshold were calibrated empirically against
the live NSF/Grants.gov corpus (136/397 real duplicates found vs. 30 with
plain exact matching), so these are tested directly rather than only
through the orchestrator.
"""

import sqlite3
from unittest.mock import MagicMock, patch

from foa_pipeline.ingestion import nsf_listing_scraper as nls


class TestNormalizeTitle:
    def test_lowercases(self):
        assert nls.normalize_title("Ocean Sciences Program") == "ocean sciences program"

    def test_strips_parenthetical_acronym(self):
        result = nls.normalize_title("Bioinnovation and Infrastructure (BI)")
        assert result == "bioinnovation and infrastructure"

    def test_strips_fy_prefix(self):
        assert "fy26" not in nls.normalize_title("FY26 Research Program")
        assert "fy 2026" not in nls.normalize_title("FY 2026 Research Program")

    def test_strips_fiscal_year_phrase(self):
        result = nls.normalize_title("Fiscal Year 2026 Cooperating Technical Partners")
        assert "fiscal year 2026" not in result

    def test_collapses_whitespace(self):
        assert nls.normalize_title("A   Program    Title") == "a program title"

    def test_empty_string(self):
        assert nls.normalize_title("") == ""


class TestIsLikelyDuplicate:
    def test_exact_normalized_match(self):
        existing = [nls.normalize_title("Ocean Sciences Program")]
        assert nls.is_likely_duplicate("Ocean Sciences Program", existing) is True

    def test_near_duplicate_via_acronym_difference(self):
        """The exact real case that motivated the fuzzy fallback."""
        existing = [nls.normalize_title("CyberAICorps Scholarship for Service")]
        assert nls.is_likely_duplicate(
            "CyberAICorps Scholarship for Service (CyberAI SFS)", existing
        ) is True

    def test_genuinely_different_titles_not_matched(self):
        existing = [nls.normalize_title("Ocean Sciences Program")]
        assert nls.is_likely_duplicate("Atmospheric and Geospace Sciences", existing) is False

    def test_empty_existing_list_never_matches(self):
        assert nls.is_likely_duplicate("Anything at all", []) is False

    def test_empty_title_never_matches(self):
        existing = [nls.normalize_title("Ocean Sciences Program")]
        assert nls.is_likely_duplicate("", existing) is False

    def test_threshold_is_configurable(self):
        existing = ["completely different words here"]
        title = "different words entirely"
        # A weak partial overlap shouldn't match at a strict threshold...
        assert nls.is_likely_duplicate(title, existing, threshold=0.99) is False
        # ...but should at a very permissive one.
        assert nls.is_likely_duplicate(title, existing, threshold=0.3) is True


class TestExtractListingRows:
    def test_filters_rows_missing_title_or_href(self):
        page = MagicMock()
        page.eval_on_selector_all.return_value = [
            {"title": "Real Program", "href": "https://www.nsf.gov/funding/opportunities/real"},
            {"title": "", "href": "https://www.nsf.gov/funding/opportunities/no-title"},
            {"title": "No Link", "href": ""},
        ]
        rows = nls._extract_listing_rows(page)
        assert len(rows) == 1
        assert rows[0]["title"] == "Real Program"


class TestLastPageIndex:
    def test_finds_max_page_number(self):
        page = MagicMock()
        page.eval_on_selector_all.return_value = [
            "https://www.nsf.gov/funding/opportunities?page=1",
            "https://www.nsf.gov/funding/opportunities?page=15",
            "https://www.nsf.gov/funding/opportunities?page=3",
        ]
        assert nls._last_page_index(page) == 15

    def test_no_pager_links_means_single_page(self):
        page = MagicMock()
        page.eval_on_selector_all.return_value = []
        assert nls._last_page_index(page) == 0


class TestExistingNormalizedTitles:
    def _insert_foa(self, db_path, title, source_id):
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT INTO foa_records
               (foa_id, source, source_id, title, status, ingestion_date, last_updated)
               VALUES (?, 'grants_gov', ?, ?, 'open', 'x', 'x')""",
            (f"id-{source_id}", source_id, title),
        )
        conn.commit()
        conn.close()

    def test_reads_titles_across_all_sources(self, test_config):
        from foa_pipeline.storage.database import Database

        Database(test_config.app_db_path).close()  # create schema
        self._insert_foa(test_config.app_db_path, "Ocean Sciences Program", "1")
        self._insert_foa(test_config.app_db_path, "Atmospheric Sciences (AGS)", "2")

        titles = nls._existing_normalized_titles(test_config.app_db_path)
        assert "ocean sciences program" in titles
        assert "atmospheric sciences" in titles


class TestDiscoverNsfListings:
    def _mock_playwright(self, mock_sync_playwright, pager_hrefs, listing_rows):
        mock_page = MagicMock()
        mock_page.eval_on_selector_all.side_effect = lambda selector, *_a, **_k: (
            pager_hrefs if "page=" in selector else listing_rows
        )
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        return mock_page, mock_browser

    @patch("playwright.sync_api.sync_playwright")
    def test_queues_new_and_skips_duplicates(self, mock_sync_playwright, test_config):
        from foa_pipeline.storage.database import Database

        Database(test_config.app_db_path).close()
        conn = sqlite3.connect(test_config.app_db_path)
        conn.execute(
            """INSERT INTO foa_records
               (foa_id, source, source_id, title, status, ingestion_date, last_updated)
               VALUES ('id-1', 'grants_gov', '1', 'Ocean Sciences Program', 'open', 'x', 'x')"""
        )
        conn.commit()
        conn.close()

        self._mock_playwright(
            mock_sync_playwright,
            pager_hrefs=[],  # single page
            listing_rows=[
                {"title": "Ocean Sciences Program", "href": "/funding/opportunities/ocean"},
                {"title": "Brand New Programme", "href": "/funding/opportunities/new-one"},
            ],
        )

        stats = nls.discover_nsf_listings(test_config)

        assert stats["pages_crawled"] == 1
        assert stats["listings_seen"] == 2
        assert stats["duplicates_skipped"] == 1
        assert stats["queued"] == 1

        conn = sqlite3.connect(test_config.sqlite_db_path)
        rows = conn.execute("SELECT url, source FROM pending_urls").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "https://www.nsf.gov/funding/opportunities/new-one"
        assert rows[0][1] == "nsf_listing"

    @patch("playwright.sync_api.sync_playwright")
    def test_dry_run_queues_nothing(self, mock_sync_playwright, test_config):
        from foa_pipeline.storage.database import Database

        Database(test_config.app_db_path).close()
        self._mock_playwright(
            mock_sync_playwright,
            pager_hrefs=[],
            listing_rows=[{"title": "New Programme", "href": "/funding/opportunities/new"}],
        )

        stats = nls.discover_nsf_listings(test_config, dry_run=True)
        assert stats["queued"] == 0

        conn = sqlite3.connect(test_config.sqlite_db_path)
        # dry_run should still create the table but insert nothing
        count = conn.execute("SELECT COUNT(*) FROM pending_urls").fetchone()[0]
        conn.close()
        assert count == 0

    @patch("playwright.sync_api.sync_playwright")
    def test_same_url_not_queued_twice_across_runs(self, mock_sync_playwright, test_config):
        from foa_pipeline.storage.database import Database

        Database(test_config.app_db_path).close()
        self._mock_playwright(
            mock_sync_playwright,
            pager_hrefs=[],
            listing_rows=[{"title": "New Programme", "href": "/funding/opportunities/new"}],
        )

        first = nls.discover_nsf_listings(test_config)
        second = nls.discover_nsf_listings(test_config)

        assert first["queued"] == 1
        assert second["queued"] == 0  # already in pending_urls, INSERT OR IGNORE
