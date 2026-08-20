"""
NSF Funding-Search Listing Scraper.

Discovers NSF funding opportunities by paginating through nsf.gov's own
funding-search results page, not just the RSS "what's new" feed nsf_rss.py
polls. The RSS feed is a small rolling window of recently-posted/updated
items -- confirmed empirically: 21 entries in the live feed, versus 397 in
the full search results at the same time. A programme that's been open for
months without an edit never appears in the feed and is otherwise invisible
to this pipeline.

Scrapes the rendered listing page directly (Playwright, matching
nsf_scraper.py's approach) rather than NSF's internal CSV export endpoint --
the search page returns a bot-check response to a plain HTTP client and
needs a real browser with a realistic User-Agent to render.

Newly-discovered URLs are queued into the same `pending_urls` table
nsf_rss.py already populates, so the existing drain_nsf_queue() detail-page
scraper needs no changes to process them; this module is discovery only.

Deduplicates against every FOA already ingested from any source (mainly
Grants.gov, which does carry some NSF-attributed opportunities) using
normalized + fuzzy title matching. Exact string matching alone catches only
30/397 real duplicates -- NSF and Grants.gov title the same programme
differently often enough (parenthetical acronyms, FY prefixes, minor
rewording) that a plain comparison misses most of them; calibrated
empirically against the live corpus before picking the 0.85 threshold.
"""

import difflib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urljoin

from ..config import Config
from ..storage.database import Database

logger = logging.getLogger(__name__)

NSF_LISTING_BASE_URL = "https://www.nsf.gov/funding/opportunities"
DUPLICATE_TITLE_THRESHOLD = 0.85

# nsf.gov's search page returns a bot-check response (HTTP 202, empty body)
# to a plain HTTP client or an unrealistic UA; a normal desktop Chrome UA
# through a real browser gets through cleanly.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

_ACRONYM_RE = re.compile(r"\(\w+\)")
_FY_RE = re.compile(r"\bfy\s?\d{2,4}\b")
_FISCAL_YEAR_RE = re.compile(r"\bfiscal year \d{4}\b")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip parenthetical acronyms/FY prefixes/punctuation.

    NSF and Grants.gov title the same programme differently often enough
    (e.g. "CyberAICorps Scholarship for Service (CyberAI SFS)" vs
    "CyberAICorps Scholarship for Service") that this alone resolves most
    duplicates without needing the fuzzy-ratio fallback.
    """
    t = title.lower()
    t = _ACRONYM_RE.sub(" ", t)
    t = _FY_RE.sub(" ", t)
    t = _FISCAL_YEAR_RE.sub(" ", t)
    t = _NON_ALNUM_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


def is_likely_duplicate(
    title: str, existing_normalized_titles: List[str], threshold: float = DUPLICATE_TITLE_THRESHOLD
) -> bool:
    """Whether `title` is probably already covered by an existing FOA.

    Checks normalized-exact first (cheap, catches most real duplicates),
    then falls back to the best fuzzy ratio against every existing title.
    """
    if not existing_normalized_titles:
        return False
    normalized = normalize_title(title)
    if not normalized:
        return False
    if normalized in existing_normalized_titles:
        return True
    best_ratio = max(
        difflib.SequenceMatcher(None, normalized, other).ratio()
        for other in existing_normalized_titles
    )
    return best_ratio >= threshold


def _existing_normalized_titles(db_path) -> List[str]:
    """Normalized titles of every FOA already ingested, across all sources."""
    db = Database(db_path)
    try:
        rows = db.conn.execute("SELECT title FROM foa_records").fetchall()
    finally:
        db.close()
    return [normalize_title(row["title"]) for row in rows if row["title"]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_urls (
            url TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            scraped_at TEXT
        )
        """
    )
    conn.commit()


def _last_page_index(page) -> int:
    """Highest `?page=N` value linked from the pager, so the crawl covers
    however many pages currently exist rather than a hardcoded count."""
    hrefs = page.eval_on_selector_all("a[href*='page=']", "els => els.map(e => e.href)")
    pages = [int(m.group(1)) for href in hrefs if (m := re.search(r"[?&]page=(\d+)", href))]
    return max(pages) if pages else 0


def _extract_listing_rows(page) -> List[Dict[str, str]]:
    rows = page.eval_on_selector_all(
        ".views-row",
        """els => els.map(e => {
            const a = e.querySelector('.teaser--title a');
            return { title: a ? a.textContent.trim() : '', href: a ? a.href : '' };
        })""",
    )
    return [r for r in rows if r["title"] and r["href"]]


def discover_nsf_listings(config: Config, *, dry_run: bool = False) -> Dict[str, int]:
    """
    Crawl every page of NSF's funding-search results and queue genuinely
    new opportunities (not already covered by another source, by fuzzy
    title match) for the existing detail-page scraper to process.
    """
    from playwright.sync_api import sync_playwright

    existing_normalized = _existing_normalized_titles(config.app_db_path)
    logger.info("Comparing against %d existing FOA titles for dedup", len(existing_normalized))

    stats = {"pages_crawled": 0, "listings_seen": 0, "duplicates_skipped": 0, "queued": 0}
    conn = sqlite3.connect(config.sqlite_db_path)
    try:
        _ensure_schema(conn)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()

            page.goto(f"{NSF_LISTING_BASE_URL}?page=0", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)
            last_page = _last_page_index(page)
            logger.info("NSF funding search currently has %d pages", last_page + 1)

            for page_num in range(0, last_page + 1):
                if page_num > 0:
                    page.goto(
                        f"{NSF_LISTING_BASE_URL}?page={page_num}",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    page.wait_for_timeout(800)

                stats["pages_crawled"] += 1
                rows = _extract_listing_rows(page)
                stats["listings_seen"] += len(rows)
                logger.info("Page %d: %d listings", page_num, len(rows))

                for row in rows:
                    if is_likely_duplicate(row["title"], existing_normalized):
                        stats["duplicates_skipped"] += 1
                        continue

                    if dry_run:
                        continue

                    url = urljoin(NSF_LISTING_BASE_URL, row["href"])
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO pending_urls (url, source, seen_at) "
                        "VALUES (?, ?, ?)",
                        (url, "nsf_listing", _iso_now()),
                    )
                    if cursor.rowcount > 0:
                        stats["queued"] += 1

            browser.close()

        conn.commit()
    finally:
        conn.close()

    return stats
