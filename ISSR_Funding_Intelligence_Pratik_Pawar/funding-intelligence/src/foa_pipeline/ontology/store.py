"""
SQLite-backed ontology store for semantic tagging concepts.

Manages:
- GREAT Act Mission Categories (sponsor_theme)
- UN SDG Goals + Targets (research_domain)
- Research Methods/Approaches (method)
- Target Populations (population)
- Synonym expansions (WordNet + manual)
- Hierarchical concept relationships (parent → child)

The store is loaded once at startup and queried by the tagging pipeline.
"""

import csv
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OntologyConcept:
    """A single concept in the tagging ontology."""

    concept_id: str
    label: str
    category: str       # research_domain | method | population | sponsor_theme
    parent_id: Optional[str]
    source_ontology: str  # un_sdg | great_act | custom
    description: Optional[str]
    synonyms: List[str] = field(default_factory=list)


class OntologyStore:
    """SQLite-backed ontology concept store."""

    def __init__(self, db_path: Path, check_same_thread: bool = True):
        """
        `check_same_thread=False` is for long-lived, read-only callers such as
        the API's cached TaggerPipeline (see api/deps.py). FastAPI dispatches
        sync routes onto a threadpool, so a store cached once at process
        startup will be used from a different thread on every request; after
        `TaggerPipeline.initialize()` this store only serves read-only
        crosswalk/hierarchy lookups against reference data that the running
        API never writes to, so there is no concurrent-write hazard to guard
        against. Every other caller (CLI commands, `setup-ontology`, tests)
        keeps the default, since sqlite3's same-thread check is a real safety
        net when a connection might see concurrent writes.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create ontology tables if they don't exist."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ontology_concepts (
                concept_id      TEXT PRIMARY KEY,
                label           TEXT NOT NULL,
                category        TEXT NOT NULL,
                parent_id       TEXT,
                source_ontology TEXT NOT NULL,
                description     TEXT,
                embedding_index INTEGER
            );

            CREATE TABLE IF NOT EXISTS ontology_synonyms (
                synonym     TEXT NOT NULL,
                concept_id  TEXT NOT NULL,
                source      TEXT NOT NULL DEFAULT 'wordnet',
                PRIMARY KEY (synonym, concept_id)
            );

            CREATE TABLE IF NOT EXISTS cfda_crosswalk (
                cfda_number TEXT PRIMARY KEY,
                concept_id  TEXT NOT NULL,
                agency_code TEXT
            );
            """
        )
        self.conn.commit()

    def load_from_csv(self, csv_path: Path, source_ontology: str) -> int:
        """
        Load ontology concepts from a CSV file.

        CSV columns: concept_id, label, category, parent_id, description
        """
        count = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.conn.execute(
                    """INSERT OR REPLACE INTO ontology_concepts
                       (concept_id, label, category, parent_id, source_ontology, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        row["concept_id"],
                        row["label"],
                        row["category"],
                        row.get("parent_id") or None,
                        source_ontology,
                        row.get("description"),
                    ),
                )
                count += 1
        self.conn.commit()
        logger.info("Loaded %d concepts from %s (%s)", count, csv_path.name, source_ontology)
        return count

    def load_all_ontologies(self, ontology_dir: Path) -> Dict[str, int]:
        """Load all ontology CSV files from a directory."""
        stats: Dict[str, int] = {}

        file_source_map = {
            "great_act_categories.csv": "great_act",
            "un_sdg_goals.csv": "un_sdg",
            "research_methods.csv": "custom",
            "populations.csv": "custom",
            "nsf_directorates.csv": "nsf",
        }

        for filename, source in file_source_map.items():
            csv_path = ontology_dir / filename
            if csv_path.exists():
                stats[filename] = self.load_from_csv(csv_path, source)
            else:
                logger.warning("Ontology file not found: %s", csv_path)
                stats[filename] = 0

        return stats

    def add_synonyms(
        self, concept_id: str, synonyms: List[str], source: str = "wordnet"
    ) -> int:
        """Add synonym entries for a concept."""
        count = 0
        for syn in synonyms:
            syn_lower = syn.lower().strip()
            if not syn_lower:
                continue
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO ontology_synonyms VALUES (?, ?, ?)",
                    (syn_lower, concept_id, source),
                )
                count += 1
            except sqlite3.Error:
                pass
        self.conn.commit()
        return count

    def get_all_concepts(self) -> List[OntologyConcept]:
        """Load all concepts with their synonyms."""
        concepts = []
        rows = self.conn.execute("SELECT * FROM ontology_concepts").fetchall()
        for row in rows:
            syns = self.conn.execute(
                "SELECT synonym FROM ontology_synonyms WHERE concept_id = ?",
                (row["concept_id"],),
            ).fetchall()
            concepts.append(
                OntologyConcept(
                    concept_id=row["concept_id"],
                    label=row["label"],
                    category=row["category"],
                    parent_id=row["parent_id"],
                    source_ontology=row["source_ontology"],
                    description=row["description"],
                    synonyms=[s["synonym"] for s in syns],
                )
            )
        return concepts

    def get_concepts_by_category(self, category: str) -> List[OntologyConcept]:
        """Get all concepts in a specific category."""
        rows = self.conn.execute(
            "SELECT * FROM ontology_concepts WHERE category = ?", (category,)
        ).fetchall()
        concepts = []
        for row in rows:
            syns = self.conn.execute(
                "SELECT synonym FROM ontology_synonyms WHERE concept_id = ?",
                (row["concept_id"],),
            ).fetchall()
            concepts.append(
                OntologyConcept(
                    concept_id=row["concept_id"],
                    label=row["label"],
                    category=row["category"],
                    parent_id=row["parent_id"],
                    source_ontology=row["source_ontology"],
                    description=row["description"],
                    synonyms=[s["synonym"] for s in syns],
                )
            )
        return concepts

    def get_concept_by_id(self, concept_id: str) -> Optional[OntologyConcept]:
        """Get a single concept by ID."""
        row = self.conn.execute(
            "SELECT * FROM ontology_concepts WHERE concept_id = ?",
            (concept_id,),
        ).fetchone()
        if not row:
            return None
        syns = self.conn.execute(
            "SELECT synonym FROM ontology_synonyms WHERE concept_id = ?",
            (concept_id,),
        ).fetchall()
        return OntologyConcept(
            concept_id=row["concept_id"],
            label=row["label"],
            category=row["category"],
            parent_id=row["parent_id"],
            source_ontology=row["source_ontology"],
            description=row["description"],
            synonyms=[s["synonym"] for s in syns],
        )

    def get_children(self, parent_id: str) -> List[OntologyConcept]:
        """Get child concepts for hierarchical propagation."""
        rows = self.conn.execute(
            "SELECT * FROM ontology_concepts WHERE parent_id = ?",
            (parent_id,),
        ).fetchall()
        return [
            OntologyConcept(
                concept_id=r["concept_id"],
                label=r["label"],
                category=r["category"],
                parent_id=r["parent_id"],
                source_ontology=r["source_ontology"],
                description=r["description"],
                synonyms=[],
            )
            for r in rows
        ]

    def get_parent_chain(self, concept_id: str) -> List[str]:
        """
        Get the chain of parent concept IDs for hierarchical propagation.
        If a child SDG target matches, this returns the parent SDG Goal ID.
        """
        chain: List[str] = []
        current = concept_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            concept = self.get_concept_by_id(current)
            if not concept or not concept.parent_id:
                break
            chain.append(concept.parent_id)
            current = concept.parent_id
        return chain

    def concept_count(self) -> int:
        """Get the total number of concepts in the store."""
        row = self.conn.execute("SELECT COUNT(*) FROM ontology_concepts").fetchone()
        return row[0] if row else 0

    def synonym_count(self) -> int:
        """Get the total number of synonyms in the store."""
        row = self.conn.execute("SELECT COUNT(*) FROM ontology_synonyms").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
