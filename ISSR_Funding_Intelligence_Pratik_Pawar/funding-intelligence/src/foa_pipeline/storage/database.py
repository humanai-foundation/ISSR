"""
Application database layer for the ISSR Funding Intelligence platform.

Provides CRUD operations for FOA records, tags, and FAISS metadata
using SQLite as the backing store.

Designed for single-user / small-team usage at ISSR scale (~10K FOAs).
If scaling is needed later, swap SQLite for PostgreSQL with minimal changes.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DB_SCHEMA = """
-- Core FOA Storage
CREATE TABLE IF NOT EXISTS foa_records (
    foa_id              TEXT PRIMARY KEY,
    source              TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    source_url          TEXT,
    title               TEXT NOT NULL,
    agency              TEXT,
    agency_code         TEXT,
    opportunity_number  TEXT,
    posted_date         TEXT,
    close_date          TEXT,
    archive_date        TEXT,
    status              TEXT NOT NULL,
    funding_instrument  TEXT,
    award_floor         REAL,
    award_ceiling       REAL,
    expected_awards     INTEGER,
    estimated_funding   REAL,
    program_description TEXT,
    eligibility_description TEXT,
    additional_info     TEXT,
    funding_tiers       TEXT,
    ingestion_date      TEXT NOT NULL,
    last_updated        TEXT NOT NULL,
    raw_payload         TEXT,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_foa_status ON foa_records(status);
CREATE INDEX IF NOT EXISTS idx_foa_close_date ON foa_records(close_date);
CREATE INDEX IF NOT EXISTS idx_foa_agency ON foa_records(agency_code);
CREATE INDEX IF NOT EXISTS idx_foa_posted_date ON foa_records(posted_date);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS foa_fts USING fts5(
    foa_id,
    title,
    program_description,
    eligibility_description,
    agency,
    content=foa_records,
    content_rowid=rowid
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS foa_fts_insert AFTER INSERT ON foa_records BEGIN
    INSERT INTO foa_fts(rowid, foa_id, title, program_description,
                        eligibility_description, agency)
    VALUES (new.rowid, new.foa_id, new.title, new.program_description,
            new.eligibility_description, new.agency);
END;

CREATE TRIGGER IF NOT EXISTS foa_fts_delete AFTER DELETE ON foa_records BEGIN
    INSERT INTO foa_fts(foa_fts, rowid, foa_id, title, program_description,
                        eligibility_description, agency)
    VALUES ('delete', old.rowid, old.foa_id, old.title, old.program_description,
            old.eligibility_description, old.agency);
END;

CREATE TRIGGER IF NOT EXISTS foa_fts_update AFTER UPDATE ON foa_records BEGIN
    INSERT INTO foa_fts(foa_fts, rowid, foa_id, title, program_description,
                        eligibility_description, agency)
    VALUES ('delete', old.rowid, old.foa_id, old.title, old.program_description,
            old.eligibility_description, old.agency);
    INSERT INTO foa_fts(rowid, foa_id, title, program_description,
                        eligibility_description, agency)
    VALUES (new.rowid, new.foa_id, new.title, new.program_description,
            new.eligibility_description, new.agency);
END;

-- CFDA Numbers (many-to-many)
CREATE TABLE IF NOT EXISTS foa_cfda_numbers (
    foa_id      TEXT NOT NULL REFERENCES foa_records(foa_id) ON DELETE CASCADE,
    cfda_number TEXT NOT NULL,
    PRIMARY KEY (foa_id, cfda_number)
);

-- Eligibility Types (many-to-many)
CREATE TABLE IF NOT EXISTS foa_eligibility (
    foa_id          TEXT NOT NULL REFERENCES foa_records(foa_id) ON DELETE CASCADE,
    eligibility_type TEXT NOT NULL,
    PRIMARY KEY (foa_id, eligibility_type)
);

-- Tags (assigned to FOAs)
CREATE TABLE IF NOT EXISTS foa_tags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    foa_id          TEXT NOT NULL REFERENCES foa_records(foa_id) ON DELETE CASCADE,
    concept_id      TEXT NOT NULL,
    label           TEXT NOT NULL,
    category        TEXT NOT NULL,
    source_layer    TEXT NOT NULL,
    confidence      REAL NOT NULL,
    context_snippet TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(foa_id, concept_id, source_layer)
);

CREATE INDEX IF NOT EXISTS idx_tags_foa ON foa_tags(foa_id);
CREATE INDEX IF NOT EXISTS idx_tags_concept ON foa_tags(concept_id);
CREATE INDEX IF NOT EXISTS idx_tags_category ON foa_tags(category);

-- FAISS Index Metadata
CREATE TABLE IF NOT EXISTS faiss_metadata (
    faiss_id    INTEGER PRIMARY KEY,
    foa_id      TEXT NOT NULL REFERENCES foa_records(foa_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    UNIQUE(foa_id, chunk_index)
);
"""


class Database:
    """SQLite database wrapper for the funding intelligence application."""

    def __init__(self, db_path: Path, check_same_thread: bool = True):
        """
        `check_same_thread=False` is for the API's get_db() dependency
        (api/deps.py). Each request there gets its own freshly opened
        Database -- never shared or cached across requests -- so there is no
        real concurrent-access hazard to guard against. The default's
        same-thread check still trips, though: Starlette's BaseHTTPMiddleware
        (this API's RateLimitMiddleware included) can run a sync generator
        dependency's `yield` and its `finally` cleanup on different
        threadpool workers within one request's lifecycle, and sqlite3
        raises unconditionally on that even though it isn't the cross-request
        race the check exists to catch. Confirmed by reproducing it: a
        request succeeded (200, real data) and still 500'd because db.close()
        in the `finally` landed on a different OS thread than the one that
        opened the connection. Every other caller (CLI commands, evaluation
        scripts) keeps the default, since those are genuinely single-threaded
        and the check is a real safety net there.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create all tables if they don't exist."""
        self.conn.executescript(_DB_SCHEMA)
        self.conn.commit()

    # ═══════════════════════════════════════════
    # FOA Record CRUD
    # ═══════════════════════════════════════════

    def upsert_foa(self, record: Dict[str, Any]) -> bool:
        """
        Insert or update a FOA record.
        Returns True if the record was newly inserted, False if updated.
        """
        source = record.get("source")
        source_id = record.get("source_id")

        existing_row = self.conn.execute(
            "SELECT foa_id FROM foa_records WHERE source = ? AND source_id = ?",
            (source, source_id)
        ).fetchone()

        raw_payload_json = json.dumps(record.get("raw_payload", {}))
        funding_tiers_json = json.dumps(record.get("funding_tiers", []))

        if existing_row:
            foa_id = existing_row["foa_id"]
            record["foa_id"] = foa_id  # ensure record uses the existing ID
            self.conn.execute(
                """UPDATE foa_records SET
                    source_url=?, title=?, agency=?, agency_code=?,
                    opportunity_number=?, posted_date=?, close_date=?,
                    archive_date=?, status=?, funding_instrument=?,
                    award_floor=?, award_ceiling=?, expected_awards=?,
                    estimated_funding=?, program_description=?,
                    eligibility_description=?, additional_info=?, funding_tiers=?,
                    last_updated=?, raw_payload=?
                WHERE foa_id=?""",
                (
                    record.get("source_url"),
                    record.get("title"),
                    record.get("agency"),
                    record.get("agency_code"),
                    record.get("opportunity_number"),
                    record.get("posted_date"),
                    record.get("close_date"),
                    record.get("archive_date"),
                    record.get("status"),
                    record.get("funding_instrument"),
                    record.get("award_floor"),
                    record.get("award_ceiling"),
                    record.get("expected_awards"),
                    record.get("estimated_funding"),
                    record.get("program_description"),
                    record.get("eligibility_description"),
                    record.get("additional_info"),
                    funding_tiers_json,
                    datetime.now(timezone.utc).isoformat(),
                    raw_payload_json,
                    foa_id,
                ),
            )
            is_new = False
        else:
            foa_id = record["foa_id"]
            self.conn.execute(
                """INSERT INTO foa_records (
                    foa_id, source, source_id, source_url, title, agency,
                    agency_code, opportunity_number, posted_date, close_date,
                    archive_date, status, funding_instrument, award_floor,
                    award_ceiling, expected_awards, estimated_funding,
                    program_description, eligibility_description, additional_info,
                    funding_tiers, ingestion_date, last_updated, raw_payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    foa_id,
                    record.get("source"),
                    record.get("source_id"),
                    record.get("source_url"),
                    record.get("title"),
                    record.get("agency"),
                    record.get("agency_code"),
                    record.get("opportunity_number"),
                    record.get("posted_date"),
                    record.get("close_date"),
                    record.get("archive_date"),
                    record.get("status"),
                    record.get("funding_instrument"),
                    record.get("award_floor"),
                    record.get("award_ceiling"),
                    record.get("expected_awards"),
                    record.get("estimated_funding"),
                    record.get("program_description"),
                    record.get("eligibility_description"),
                    record.get("additional_info"),
                    funding_tiers_json,
                    record.get("ingestion_date", datetime.now(timezone.utc).isoformat()),
                    datetime.now(timezone.utc).isoformat(),
                    raw_payload_json,
                ),
            )
            is_new = True

        # Update CFDA numbers
        self.conn.execute("DELETE FROM foa_cfda_numbers WHERE foa_id=?", (foa_id,))
        for cfda in record.get("cfda_numbers", []):
            self.conn.execute(
                "INSERT OR IGNORE INTO foa_cfda_numbers VALUES (?, ?)",
                (foa_id, cfda),
            )

        # Update eligibility
        self.conn.execute("DELETE FROM foa_eligibility WHERE foa_id=?", (foa_id,))
        for elig in record.get("eligibility", []):
            if elig:
                self.conn.execute(
                    "INSERT OR IGNORE INTO foa_eligibility VALUES (?, ?)",
                    (foa_id, elig),
                )

        self.conn.commit()
        return is_new

    def get_foas_with_unprocessed_pdfs(self) -> List[Dict[str, Any]]:
        """Find FOAs that have PDF links in their raw payload but haven't been parsed yet."""
        rows = self.conn.execute(
            """SELECT foa_id, raw_payload, program_description
               FROM foa_records
               WHERE raw_payload IS NOT NULL
               AND raw_payload NOT LIKE '%"pdf_processed": true%'"""
        ).fetchall()

        foas = []
        for row in rows:
            try:
                # Sometimes payload is double-encoded
                raw = row["raw_payload"] or "{}"
                payload = json.loads(raw)
                if isinstance(payload, str):
                    payload = json.loads(payload)

                if payload.get("pdf_links") and not payload.get("pdf_processed"):
                    foas.append({
                        "foa_id": row["foa_id"],
                        "pdf_links": payload["pdf_links"],
                        "program_description": row["program_description"] or ""
                    })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to decode payload for %s: %s", row["foa_id"], e
                )
                continue
        return foas

    def append_to_program_description(
        self, foa_id: str, appended_text: str, mark_pdf_processed: bool = True
    ) -> None:
        """Append text to an FOA's program description and optionally mark PDFs as processed."""
        row = self.conn.execute(
            "SELECT program_description, raw_payload FROM foa_records WHERE foa_id = ?",
            (foa_id,),
        ).fetchone()
        if not row:
            return

        new_desc = (row["program_description"] or "") + "\n\n" + appended_text

        payload = {}
        if mark_pdf_processed and row["raw_payload"]:
            try:
                payload = json.loads(row["raw_payload"])
                payload["pdf_processed"] = True
            except json.JSONDecodeError:
                pass

        new_payload = json.dumps(payload) if payload else row["raw_payload"]

        self.conn.execute(
            """UPDATE foa_records
               SET program_description = ?, raw_payload = ?, last_updated = CURRENT_TIMESTAMP
               WHERE foa_id = ?""",
            (new_desc, new_payload, foa_id)
        )
        self.conn.commit()

    def get_foa(self, foa_id: str) -> Optional[Dict[str, Any]]:
        """Get a single FOA record by ID, including tags."""
        row = self.conn.execute(
            "SELECT * FROM foa_records WHERE foa_id = ?", (foa_id,)
        ).fetchone()
        if not row:
            return None
        record = dict(row)
        record["raw_payload"] = json.loads(record.get("raw_payload") or "{}")
        record["funding_tiers"] = json.loads(record.get("funding_tiers") or "[]")

        # Attach CFDA numbers
        cfdas = self.conn.execute(
            "SELECT cfda_number FROM foa_cfda_numbers WHERE foa_id=?", (foa_id,)
        ).fetchall()
        record["cfda_numbers"] = [c["cfda_number"] for c in cfdas]

        # Attach eligibility
        eligs = self.conn.execute(
            "SELECT eligibility_type FROM foa_eligibility WHERE foa_id=?", (foa_id,)
        ).fetchall()
        record["eligibility"] = [e["eligibility_type"] for e in eligs]

        # Attach tags
        record["tags"] = self.get_tags_for_foa(foa_id)

        return record

    # Dimensions get_facet_counts() reports on. Kept in step with the filters
    # list_foas() actually accepts -- add a column here only once list_foas
    # (and _build_where_clause below) also filters on it, so the sidebar
    # never offers a facet that filtering it wouldn't act on.
    FACET_DIMENSIONS = ("status", "agency_code")

    def _build_where_clause(
        self,
        *,
        status: Optional[str] = None,
        agency_code: Optional[str] = None,
        exclude: Optional[str] = None,
    ) -> Tuple[str, List[Any]]:
        """
        Shared WHERE-clause builder for list_foas() and get_facet_counts(),
        so the two can't drift apart on what "status"/"agency_code" mean.

        `exclude` omits one dimension's own clause. Facet counts must reflect
        every OTHER active filter, not the one they're counting toward --
        counting agency options while already filtered to a single agency
        would make every other agency read zero, which is not what a
        faceted sidebar is for.
        """
        where_clauses = []
        params: List[Any] = []

        if status and exclude != "status":
            where_clauses.append("status = ?")
            params.append(status)
        if agency_code and exclude != "agency_code":
            where_clauses.append("agency_code = ?")
            params.append(agency_code)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        return where_sql, params

    def get_facet_counts(
        self,
        *,
        status: Optional[str] = None,
        agency_code: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Per-dimension counts for the sidebar facets (GET /api/opportunities/facets).

        Each dimension is computed against every OTHER currently-active
        filter, via `exclude` on the shared WHERE builder -- real facet
        semantics, matching how a faceted search UI (grants.gov included) is
        expected to behave: narrowing by status should not make every agency
        option but the selected one read zero.
        """
        facets: Dict[str, List[Dict[str, Any]]] = {}
        for dim in self.FACET_DIMENSIONS:
            where_sql, params = self._build_where_clause(
                status=status, agency_code=agency_code, exclude=dim
            )
            rows = self.conn.execute(
                f"""SELECT {dim} AS value, COUNT(*) AS count FROM foa_records
                    WHERE {where_sql} AND {dim} IS NOT NULL
                    GROUP BY {dim}
                    ORDER BY count DESC""",
                params,
            ).fetchall()
            facets[dim] = [{"value": r["value"], "count": r["count"]} for r in rows]
        return facets

    def list_foas(
        self,
        *,
        status: Optional[str] = None,
        agency_code: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "posted_date",
        sort_order: str = "DESC",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List FOA records with filtering, pagination, and sorting.
        Returns (records, total_count).
        """
        where_sql, params = self._build_where_clause(
            status=status, agency_code=agency_code
        )

        # Validate sort column
        allowed_sorts = {
            "posted_date", "close_date", "title", "agency",
            "award_ceiling", "award_floor", "ingestion_date",
        }
        if sort_by not in allowed_sorts:
            sort_by = "posted_date"
        if sort_order.upper() not in ("ASC", "DESC"):
            sort_order = "DESC"

        # Count
        count_row = self.conn.execute(
            f"SELECT COUNT(*) FROM foa_records WHERE {where_sql}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        # Fetch page
        offset = (page - 1) * size
        rows = self.conn.execute(
            f"""SELECT * FROM foa_records
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order} NULLS LAST
                LIMIT ? OFFSET ?""",
            params + [size, offset],
        ).fetchall()

        records = []
        for row in rows:
            record = dict(row)
            record["raw_payload"] = json.loads(record.get("raw_payload") or "{}")
            record["funding_tiers"] = json.loads(record.get("funding_tiers") or "[]")
            record["tags"] = self.get_tags_for_foa(record["foa_id"])
            records.append(record)

        return records, total

    def search_fts(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        agency_code: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Full-text search using FTS5."""
        # Quoted as a single FTS5 phrase literal so operator syntax in raw
        # user input -- a leading "-", an unmatched '"' -- can't reach the
        # query parser and raise sqlite3.OperationalError. FTS5 escapes an
        # internal '"' by doubling it. The web rewrite makes this the app's
        # primary top-of-page interaction, so it needs to survive arbitrary
        # typing rather than 500 on it.
        fts_query = '"' + query.replace('"', '""') + '"'
        params: List[Any] = [fts_query]
        extra_where = ""
        if status:
            extra_where += " AND r.status = ?"
            params.append(status)
        if agency_code:
            extra_where += " AND r.agency_code = ?"
            params.append(agency_code)

        # Count
        count_sql = f"""
            SELECT COUNT(*) FROM foa_fts f
            JOIN foa_records r ON f.foa_id = r.foa_id
            WHERE foa_fts MATCH ? {extra_where}
        """
        count_row = self.conn.execute(count_sql, params).fetchone()
        total = count_row[0] if count_row else 0

        # Fetch
        offset = (page - 1) * size
        fetch_sql = f"""
            SELECT r.*, rank FROM foa_fts f
            JOIN foa_records r ON f.foa_id = r.foa_id
            WHERE foa_fts MATCH ? {extra_where}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        rows = self.conn.execute(
            fetch_sql, params + [size, offset]
        ).fetchall()

        records = []
        for row in rows:
            record = dict(row)
            record.pop("rank", None)
            record["raw_payload"] = json.loads(record.get("raw_payload") or "{}")
            record["funding_tiers"] = json.loads(record.get("funding_tiers") or "[]")
            record["tags"] = self.get_tags_for_foa(record["foa_id"])
            records.append(record)

        return records, total

    # ═══════════════════════════════════════════
    # Tag Operations
    # ═══════════════════════════════════════════

    def save_tags(self, foa_id: str, tags: List[Dict[str, Any]]) -> int:
        """Save tag evidence records for an FOA."""
        count = 0
        for tag in tags:
            try:
                self.conn.execute(
                    """INSERT OR REPLACE INTO foa_tags
                       (foa_id, concept_id, label, category, source_layer,
                        confidence, context_snippet)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        foa_id,
                        tag.get("ontology_concept_id", tag.get("concept_id", "")),
                        tag.get("label", ""),
                        tag.get("category", ""),
                        tag.get("source_layer", ""),
                        tag.get("confidence", 0.0),
                        tag.get("context_snippet", ""),
                    ),
                )
                count += 1
            except sqlite3.Error as exc:
                logger.warning("Failed to save tag for %s: %s", foa_id, exc)
        self.conn.commit()
        return count

    def get_tags_for_foa(self, foa_id: str) -> List[Dict[str, Any]]:
        """Get all tags for an FOA."""
        rows = self.conn.execute(
            "SELECT * FROM foa_tags WHERE foa_id = ? ORDER BY confidence DESC",
            (foa_id,),
        ).fetchall()
        return [
            {
                "tag_id": f"{r['source_layer']}:{r['concept_id']}",
                "label": r["label"],
                "category": r["category"],
                "source_layer": r["source_layer"],
                "confidence": r["confidence"],
                "context_snippet": r["context_snippet"],
                "ontology_concept_id": r["concept_id"],
            }
            for r in rows
        ]

    def get_foas_by_tag(
        self, concept_id: str, page: int = 1, size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get all FOAs tagged with a specific concept."""
        count_row = self.conn.execute(
            "SELECT COUNT(DISTINCT foa_id) FROM foa_tags WHERE concept_id = ?",
            (concept_id,),
        ).fetchone()
        total = count_row[0] if count_row else 0

        offset = (page - 1) * size
        rows = self.conn.execute(
            """SELECT DISTINCT r.* FROM foa_records r
               JOIN foa_tags t ON r.foa_id = t.foa_id
               WHERE t.concept_id = ?
               ORDER BY r.posted_date DESC
               LIMIT ? OFFSET ?""",
            (concept_id, size, offset),
        ).fetchall()

        records = []
        for row in rows:
            record = dict(row)
            record["raw_payload"] = json.loads(record.get("raw_payload") or "{}")
            record["tags"] = self.get_tags_for_foa(record["foa_id"])
            records.append(record)

        return records, total

    def get_tag_stats(self) -> List[Dict[str, Any]]:
        """Get tag usage statistics grouped by category."""
        rows = self.conn.execute(
            """SELECT category, label, concept_id, COUNT(*) as count
               FROM foa_tags
               GROUP BY category, concept_id
               ORDER BY count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM foa_records").fetchone()[0]
        open_count = self.conn.execute(
            "SELECT COUNT(*) FROM foa_records WHERE status='open'"
        ).fetchone()[0]
        tag_count = self.conn.execute("SELECT COUNT(*) FROM foa_tags").fetchone()[0]
        last_row = self.conn.execute(
            "SELECT MAX(ingestion_date) FROM foa_records"
        ).fetchone()
        last_ingestion = last_row[0] if last_row else None

        return {
            "total_foas": total,
            "open_foas": open_count,
            "total_tags": tag_count,
            "last_ingestion": last_ingestion,
        }

    # ═══════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
