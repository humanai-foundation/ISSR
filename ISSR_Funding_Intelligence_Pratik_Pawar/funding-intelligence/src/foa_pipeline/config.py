import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Repo-root-relative rather than CWD-relative, since CLI commands, tests, and
# the API server are documented to run from different working directories
# (PYTHONPATH=src python -m foa_pipeline.cli ..., make serve, pytest from
# repo root) -- CWD-based discovery would silently miss .env in some of them.
# A no-op if the file doesn't exist (e.g. it was never copied from
# .env.example); _env()'s defaults still apply either way.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_COSINE_THRESHOLDS = (
    '{"method": 0.40, "population": 0.35, "research_domain": 0.35, '
    '"research_discipline": 0.35, "sponsor_theme": 0.30, "default": 0.35, '
    '"method_25": 0.65}'
)


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    # ── Grants.gov API ──
    grants_gov_base_url: str
    grants_gov_search_endpoint: str
    grants_gov_fetch_endpoint: str
    grants_gov_page_size: int
    grants_gov_max_pages: int
    grants_gov_query: str

    # ── NSF ──
    nsf_rss_url: str
    nsf_scraper_rate_limit: float
    nsf_scraper_max_concurrent: int

    # ── Paths ──
    sqlite_db_path: Path
    app_db_path: Path
    raw_output_dir: Path
    normalised_output_dir: Path
    embeddings_cache_dir: Path
    ontology_dir: Path
    evaluation_dir: Path

    # ── Tagging ──
    spacy_model: str
    embedding_model: str
    cosine_thresholds: dict
    enable_layer3_llm: bool
    ollama_base_url: str
    ollama_model: str

    # ── API ──
    api_host: str
    api_port: int
    api_reload: bool

    # ── General ──
    log_level: str
    user_agent: str
    schema_version: str

    # ── API hardening (defaulted) ──
    # These carry defaults and sit last on purpose: most of the codebase builds
    # a Config without caring about API settings, and adding a required field
    # here breaks every one of those call sites at once.
    # :3000 is the Next.js dev/prod frontend (web/) -- a separate origin from
    # this API's :8000, since the frontend now runs as its own server rather
    # than being served by this process's StaticFiles mount.
    api_cors_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:3000", "http://127.0.0.1:3000",
        ]
    )
    api_rate_limit_per_minute: int = 120
    api_export_max_rows: int = 10000

    # ── Title weighting (defaulted) ──
    # An FOA title averages 59 characters against ~3,100 of description, so it
    # is diluted to near-nothing inside a 250-word chunk. These control whether
    # Layer 2 scores it separately. 0.0 keeps the body-only behaviour.
    title_weight: float = 0.0
    title_combine: str = "blend"  # "blend" or "max"

    # ── Grant matching (defaulted) ──
    # How many top-ranked matches get an LLM-generated explanation per
    # request. Bounded deliberately: each one is an Ollama round trip
    # (seconds, not milliseconds), so explaining all of `k` would not scale
    # the way scoring them does. Tunable without a code change because the
    # right number depends on the deployment's Ollama latency.
    match_explain_top_k: int = 5

    # ── Grants.gov politeness (defaulted) ──
    # fetch_opportunity is called once per new opportunity ID with no other
    # throttle -- broadening the search from a single-agency keyword to all
    # ~26 agencies turns this into a burst of ~1,500+ sequential POSTs to a
    # public, unauthenticated government API. A small fixed delay between
    # calls is cheap insurance against soft-blocking; it does not apply to
    # search2 itself since that's at most ~30 calls per poll (max_pages).
    grants_gov_request_delay_seconds: float = 0.15

    # ── L1/L2 corroboration (defaulted) ──
    # Layer 1's exact-match confidence (always 1.0) answers "does this string
    # appear", not "is this concept what the FOA is actually about" -- e.g.
    # nsf_bio firing on a circuits/sensing FOA because "biology" appears once
    # as an application area, not the FOA's discipline. For categories listed
    # here, an L1 hit is suppressed unless Layer 2 independently scores that
    # same concept above its own threshold too (see
    # TaggerPipeline._merge_and_disambiguate). Scoped to categories where
    # Layer 2 is a reliable signal (Documentation/EVALUATION.md 4c: research_discipline AUC
    # 0.940, sponsor_theme 0.667) -- deliberately excludes method/population,
    # where Layer 2's score is worse than chance (AUC 0.476/0.400) and this
    # gate would suppress good tags rather than bad ones.
    # Empty by default: measured on the gold set and net-negative (F1 0.527 ->
    # 0.489, driven by research_discipline 0.523 -> 0.415) despite working
    # exactly as intended on the case that motivated it (see Documentation/EVALUATION.md
    # 4j). Kept, tested, and documented rather than deleted -- costs nothing
    # disabled, same treatment as title_weight above.
    l1_corroboration_categories: List[str] = field(default_factory=list)


def get_config() -> Config:
    """Build Config from environment variables with sensible defaults."""
    return Config(
        # ── Grants.gov API ──
        grants_gov_base_url=_env("GRANTS_GOV_BASE_URL", "https://api.grants.gov/v1/api"),
        grants_gov_search_endpoint=_env("GRANTS_GOV_SEARCH_ENDPOINT", "search2"),
        grants_gov_fetch_endpoint=_env("GRANTS_GOV_FETCH_ENDPOINT", "fetchOpportunity"),
        grants_gov_page_size=int(_env("GRANTS_GOV_PAGE_SIZE", "100")),
        grants_gov_max_pages=int(_env("GRANTS_GOV_MAX_PAGES", "30")),
        grants_gov_query=_env("GRANTS_GOV_QUERY", '{"oppStatuses": "forecasted|posted"}'),
        # ── NSF ──
        nsf_rss_url=_env("NSF_RSS_URL", "https://www.nsf.gov/rss/rss_www_funding.xml"),
        nsf_scraper_rate_limit=float(_env("NSF_SCRAPER_RATE_LIMIT", "1.0")),
        nsf_scraper_max_concurrent=int(_env("NSF_SCRAPER_MAX_CONCURRENT", "3")),
        # ── Paths ──
        sqlite_db_path=Path(_env("SQLITE_DB_PATH", "data/queues/nsf_queue.db")),
        app_db_path=Path(_env("APP_DB_PATH", "data/db/funding_intelligence.db")),
        raw_output_dir=Path(_env("RAW_OUTPUT_DIR", "data/raw")),
        normalised_output_dir=Path(_env("NORMALISED_OUTPUT_DIR", "data/normalised")),
        embeddings_cache_dir=Path(_env("EMBEDDINGS_CACHE_DIR", "data/embeddings")),
        ontology_dir=Path(_env("ONTOLOGY_DIR", "data/ontology")),
        evaluation_dir=Path(_env("EVALUATION_DIR", "data/evaluation")),
        # ── Tagging ──
        spacy_model=_env("SPACY_MODEL", "en_core_web_lg"),
        embedding_model=_env("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"),
        cosine_thresholds=json.loads(
            _env("COSINE_THRESHOLDS", DEFAULT_COSINE_THRESHOLDS)
        ),
        enable_layer3_llm=_env("ENABLE_LAYER3_LLM", "true").lower() == "true",
        ollama_base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=_env("OLLAMA_MODEL", "mistral:7b-instruct"),
        # ── API ──
        api_host=_env("API_HOST", "0.0.0.0"),
        api_port=int(_env("API_PORT", "8000")),
        api_reload=_env("API_RELOAD", "true").lower() == "true",
        # Comma-separated origins. The Next.js frontend (web/) runs as its own
        # server on :3000, a different origin from this API's :8000, so it
        # needs an entry here even in local dev. "*" is accepted but disables
        # credentialed requests.
        api_cors_origins=[
            o.strip()
            for o in _env(
                "API_CORS_ORIGINS",
                "http://localhost:8000,http://127.0.0.1:8000,"
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if o.strip()
        ],
        api_rate_limit_per_minute=int(_env("API_RATE_LIMIT_PER_MINUTE", "120")),
        api_export_max_rows=int(_env("API_EXPORT_MAX_ROWS", "10000")),
        # ── Title weighting ──
        title_weight=float(_env("TITLE_WEIGHT", "0.0")),
        title_combine=_env("TITLE_COMBINE", "blend"),
        # ── Grant matching ──
        match_explain_top_k=int(_env("MATCH_EXPLAIN_TOP_K", "5")),
        grants_gov_request_delay_seconds=float(
            _env("GRANTS_GOV_REQUEST_DELAY_SECONDS", "0.15")
        ),
        # Empty by default -- see the field's own comment above for why
        # (measured net-negative on the gold set, Documentation/EVALUATION.md 4j).
        l1_corroboration_categories=[
            c.strip()
            for c in _env("L1_CORROBORATION_CATEGORIES", "").split(",")
            if c.strip()
        ],
        # ── General ──
        log_level=_env("LOG_LEVEL", "INFO"),
        user_agent=_env("USER_AGENT", "foa-pipeline/1.0"),
        schema_version=_env("SCHEMA_VERSION", "1.0"),
    )
