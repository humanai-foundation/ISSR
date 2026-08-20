import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict

import feedparser

from ..config import Config

logger = logging.getLogger(__name__)


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


def poll_nsf_rss(config: Config, *, dry_run: bool = False) -> Dict[str, int]:
    feed = feedparser.parse(config.nsf_rss_url)
    if feed.bozo:
        logger.warning("RSS feed parse issue: %s", feed.bozo_exception)

    inserted = 0
    total = 0

    conn = sqlite3.connect(config.sqlite_db_path)
    try:
        _ensure_schema(conn)
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue
            total += 1
            if dry_run:
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO pending_urls (url, source, seen_at) VALUES (?, ?, ?)",
                    (link, "nsf_rss", _iso_now()),
                )
                if conn.total_changes:
                    inserted += 1
            except sqlite3.Error as exc:
                logger.warning("Failed to insert URL %s: %s", link, exc)
        conn.commit()
    finally:
        conn.close()

    return {"total": total, "inserted": inserted}
