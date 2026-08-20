"""
ISSR Funding Intelligence — FOA ingestion, semantic tagging, and grant matching.

Subpackages:
    ingestion      Source connectors (Grants.gov API, NSF RSS/scraping, PDFs)
    parsing        Layout-aware PDF and LLM field extraction
    normalisation  Canonical schema, normalisation, and validation
    ontology       Controlled vocabulary and synonym expansion
    tagging        Three-layer semantic tagging engine
    matching       Vector search and hybrid researcher-profile matching
    storage        SQLite database and JSONL helpers
    evaluation     Metrics, gold/silver evaluation, label generation
    export         CSV/JSON export for downstream consumers
    api            FastAPI application serving the web frontend
"""

import os

# faiss and spaCy/torch each ship their own OpenMP runtime. On macOS, loading
# both in one process aborts with "OMP: Error #15: Initializing libomp.dylib,
# but found libomp.dylib already initialized" (a hard SIGSEGV, no traceback) —
# which is exactly what the grant matcher does when it tags a profile with
# spaCy and then searches the FAISS index. Capping OpenMP threads before any
# of those libraries load avoids the duplicate-runtime abort. setdefault so a
# deployment can still override it.
os.environ.setdefault("OMP_NUM_THREADS", "1")

__all__ = [
    "api",
    "config",
    "evaluation",
    "export",
    "ingestion",
    "matching",
    "normalisation",
    "ontology",
    "parsing",
    "storage",
    "tagging",
]
__version__ = "1.0.0"
