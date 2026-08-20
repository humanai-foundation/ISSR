"""
NSF Website Scraper — drains the SQLite queue populated by nsf_rss.py
and scrapes actual solicitation pages from nsf.gov/funding/opportunities.

Design (Strictly compliant with Phase 1 Proposal):
- Reads pending URLs from pending_urls table (status='pending')
- Uses Crawlee + Playwright to handle JavaScript-rendered NSF pages
- For each URL:
  1. Fetch the solicitation page via headless Chromium
  2. Extract HTML content (title, description, dates, eligibility)
  3. Download any linked PDFs → pass to pdf_parser.py (downstream)
  4. Build a raw record in the canonical schema
  5. Update queue status to 'scraped' or 'failed'
"""

import asyncio
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from bs4 import BeautifulSoup

from ..config import Config
from ..normalisation.schema import build_raw_record
from ..storage.jsonl import ensure_dir, write_jsonl

# Lazy import playwright to avoid global startup overhead if not used
async_playwright = None

logger = logging.getLogger(__name__)


def load_scraping_rules(config_path: Path) -> Dict[str, Any]:
    """Load per-domain scraping rules from YAML config files."""
    rules = {}
    for yaml_file in config_path.glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        domain = yaml_file.stem
        rules[domain] = data
    return rules


# Signatures of nsf.gov's own rate-limit/bot-check response page, observed
# directly: a run without inter-batch throttling got blocked partway through
# and 261/297 pages came back as this instead of real content -- every one
# saved as a "successful" scrape, since the page load itself succeeds (200),
# it just isn't the page that was asked for.
_BLOCK_SIGNATURES = (
    "request blocked",
    "exceeded the maximum number of requests",
)


def _looks_like_a_block_page(title: Optional[str], html: str) -> bool:
    haystack = f"{title or ''} {html[:2000]}".lower()
    return any(sig in haystack for sig in _BLOCK_SIGNATURES)


def _parse_html_content(url: str, html: str) -> Optional[Dict[str, Any]]:
    """Parse the raw HTML to extract structured metadata.

    Returns None if the page is a bot-check/rate-limit response rather than
    real content, so the caller can mark it failed (and so eligible for a
    later retry) instead of silently recording it as a successful scrape.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else None

    if _looks_like_a_block_page(title, html):
        logger.warning("Blocked/rate-limited response for %s, treating as failed", url)
        return None

    # Extract description
    description = ""
    for selector in [
        "div.program-description",
        "div#programdesc",
        "div.field--name-body",
        "article",
    ]:
        desc_el = soup.select_one(selector)
        if desc_el:
            description = desc_el.get_text(separator=" ", strip=True)
            break

    if not description:
        main = soup.find("main") or soup.find("div", {"role": "main"})
        if main:
            description = main.get_text(separator=" ", strip=True)[:5000]

    # Extract dates
    dates = _extract_dates_from_html(soup)

    # Extract eligibility
    eligibility = ""
    for selector in ["div.eligibility", "div#eligibility"]:
        elig_el = soup.select_one(selector)
        if elig_el:
            eligibility = elig_el.get_text(separator=" ", strip=True)
            break

    # Extract PDF links
    pdf_links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".pdf"):
            if not href.startswith("http"):
                href = f"https://www.nsf.gov{href}"
            pdf_links.append(href)

    source_id = _extract_nsf_id(url)

    return {
        "source": "nsf_scraper",
        "source_id": source_id,
        "source_url": url,
        "title": title,
        "posted_date": dates.get("posted_date"),
        "close_date": dates.get("close_date"),
        "program_description": description,
        "eligibility_description": eligibility,
        "pdf_links": pdf_links,
        "raw_html_length": len(html),
    }


async def _run_playwright_scraper(
    urls: List[str], max_concurrent: int, rate_limit_seconds: float = 0.0
) -> Dict[str, Any]:
    """Execute the async scraper using raw Playwright.

    Bypasses Crawlee due to Python 3.14 Pydantic incompatibilities.

    `rate_limit_seconds` pauses between concurrency chunks, not within one --
    max_concurrent already bounds simultaneous requests, but nothing
    previously paced the chunks themselves. Confirmed necessary the hard
    way: an unthrottled 297-URL run got rate-limited by nsf.gov partway
    through, and every subsequent chunk came back as a bot-check page
    instead of real content (see _looks_like_a_block_page).
    """
    global async_playwright
    if async_playwright is None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright not installed. "
                "Run: pip install playwright && playwright install"
            )
            return {}

    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Process URLs concurrently in chunks
        chunk_starts = list(range(0, len(urls), max_concurrent))
        for chunk_index, i in enumerate(chunk_starts):
            chunk = urls[i:i + max_concurrent]

            async def scrape_single_url(url: str):
                logger.debug("Playwright processing: %s", url)
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                except Exception:
                    pass  # timeout is okay, continue extracting what we have

                html = await page.content()
                parsed_data = _parse_html_content(url, html)
                if parsed_data is not None:
                    results[url] = parsed_data
                await context.close()

            # Run chunk concurrently
            await asyncio.gather(*(scrape_single_url(u) for u in chunk))

            if rate_limit_seconds > 0 and chunk_index < len(chunk_starts) - 1:
                await asyncio.sleep(rate_limit_seconds)

        await browser.close()

    return results


def drain_nsf_queue(
    config: Config,
    *,
    max_pages: int = 50,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Main entry point: drain pending URLs from the SQLite queue,
    scrape each page using Crawlee + Playwright, and write normalised records.

    Returns stats: {scraped: N, failed: N, skipped: N}
    """
    stats = {"scraped": 0, "failed": 0, "skipped": 0, "total_pending": 0}

    conn = sqlite3.connect(str(config.sqlite_db_path))
    conn.row_factory = sqlite3.Row

    # Get pending URLs
    pending = conn.execute(
        "SELECT url FROM pending_urls WHERE status = 'pending' LIMIT ?",
        (max_pages,),
    ).fetchall()

    stats["total_pending"] = len(pending)
    if not pending:
        logger.info("No pending NSF URLs to scrape")
        conn.close()
        return stats

    logger.info("Found %d pending NSF URLs to scrape", len(pending))

    urls_to_scrape = [row["url"] for row in pending]

    ensure_dir(config.raw_output_dir)
    output_path = config.raw_output_dir / "nsf_scraped.jsonl"

    # Run the async crawler
    scraped_results = {}
    if not dry_run:
        try:
            # Create a new event loop if there isn't one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            scraped_results = loop.run_until_complete(
                _run_playwright_scraper(
                    urls_to_scrape,
                    config.nsf_scraper_max_concurrent,
                    rate_limit_seconds=config.nsf_scraper_rate_limit,
                )
            )
        except Exception as exc:
            logger.exception("Playwright async execution failed: %s", exc)

    # Process results and update DB
    for url in urls_to_scrape:
        if dry_run:
            stats["skipped"] += 1
            continue

        raw = scraped_results.get(url)
        if raw:
            try:
                record = build_raw_record(
                    source="nsf_scraper",
                    source_id=raw["source_id"],
                    title=raw.get("title"),
                    posted_date=raw.get("posted_date"),
                    close_date=raw.get("close_date"),
                    raw_url=url,
                    raw_payload=raw,
                )
                write_jsonl(output_path, [record])
                _update_queue_status(conn, url, "scraped")
                stats["scraped"] += 1
            except Exception as exc:
                logger.error("Error writing record for %s: %s", url, exc)
                _update_queue_status(conn, url, "failed")
                stats["failed"] += 1
        else:
            logger.warning("No data returned for %s", url)
            _update_queue_status(conn, url, "failed")
            stats["failed"] += 1

    conn.close()
    return stats


def _update_queue_status(conn: sqlite3.Connection, url: str, status: str) -> None:
    """Update a queue entry's status after processing."""
    conn.execute(
        """UPDATE pending_urls
           SET status = ?, scraped_at = ?
           WHERE url = ?""",
        (status, datetime.now(timezone.utc).isoformat(), url),
    )
    conn.commit()


def _extract_dates_from_html(soup) -> Dict[str, Optional[str]]:
    """Extract posted and close dates from HTML."""
    dates: Dict[str, Optional[str]] = {
        "posted_date": None,
        "close_date": None,
    }

    text = soup.get_text()

    # Look for deadline patterns
    deadline_pattern = r"(?:deadline|due\s+date|close\s+date)[:\s]+(\w+\s+\d{1,2},?\s+\d{4})"
    match = re.search(deadline_pattern, text, re.IGNORECASE)
    if match:
        dates["close_date"] = match.group(1)

    # Look for posted date
    posted_pattern = r"(?:posted|published|released)[:\s]+(\w+\s+\d{1,2},?\s+\d{4})"
    match = re.search(posted_pattern, text, re.IGNORECASE)
    if match:
        dates["posted_date"] = match.group(1)

    return dates


def _extract_nsf_id(url: str) -> str:
    """Extract a unique ID from an NSF URL."""
    # Try to extract solicitation number from URL
    match = re.search(r"(\d{2}-\d{3,})", url)
    if match:
        return f"NSF-{match.group(1)}"
    # Fallback: use the URL path as ID
    return url.rstrip("/").split("/")[-1]
