"""Dependency injection for FastAPI routes."""

from functools import lru_cache

from ..config import Config, get_config
from ..matching.explain import MatchExplainer
from ..matching.vector_index import VectorIndex
from ..ontology.store import OntologyStore
from ..storage.database import Database
from ..tagging.pipeline import TaggerPipeline


@lru_cache
def get_app_config() -> Config:
    """Get the application configuration (cached)."""
    return get_config()


@lru_cache
def get_vector_index() -> VectorIndex:
    """
    Load the FAISS index and embedding model once per process.

    Without this cache every semantic search re-read the index from disk and
    re-loaded the sentence-transformer model, adding seconds of latency to each
    request. Built with db=None deliberately: the index is shared across
    requests and threads, so each search is handed the request-scoped
    connection instead of holding one (SQLite connections are not shareable
    across threads).
    """
    config = get_app_config()
    index = VectorIndex(
        db=None,
        model_name=config.embedding_model,
        cache_dir=config.embeddings_cache_dir,
    )
    if index.load_index():
        index.load_model()
    return index


def get_db() -> Database:
    """
    Get a database connection. Should be used as a FastAPI dependency.

    check_same_thread=False: see Database.__init__'s docstring. A fresh
    connection is opened per request either way -- this isn't sharing one
    across requests, it's tolerating Starlette's own thread-hop between this
    generator's yield and its finally within a single request.
    """
    config = get_app_config()
    db = Database(config.app_db_path, check_same_thread=False)
    try:
        yield db
    finally:
        db.close()


@lru_cache
def get_ontology_store() -> OntologyStore:
    """
    Read-only ontology store backing the cached TaggerPipeline below.

    Opened with check_same_thread=False: FastAPI dispatches sync routes onto
    a threadpool, so this single cached connection will be used from whatever
    thread handles each request. Safe here because after initialize() the
    pipeline only issues read-only lookups against reference data the running
    API never writes to (see OntologyStore.__init__ for the full argument).
    """
    config = get_app_config()
    return OntologyStore(config.app_db_path, check_same_thread=False)


@lru_cache
def get_tagger_pipeline() -> TaggerPipeline:
    """
    Load spaCy and the embedding model once per process, matching the
    get_vector_index pattern above. Building this per-request would reload
    en_core_web_lg and the sentence-transformer model on every match request.

    Gracefully degrades if Ollama is unreachable (TaggerPipeline.initialize
    already handles this — it disables L3 rather than raising), so this is
    safe to call even where no local LLM is running.
    """
    config = get_app_config()
    pipeline = TaggerPipeline(config, get_ontology_store())
    pipeline.initialize()
    return pipeline


@lru_cache
def get_match_explainer() -> MatchExplainer:
    """
    Cached: it holds no connection, just a base URL, model name, and a
    template string read from disk once, so there is no thread-sharing
    concern the way there is for get_ontology_store.
    """
    config = get_app_config()
    template_path = config.raw_output_dir.parent / "prompts" / "match_explanation.txt"
    return MatchExplainer(
        base_url=config.ollama_base_url,
        model=config.ollama_model,
        prompt_template_path=template_path,
    )
