"""
FastAPI application factory.

Serves the FOA data through a REST API consumed by the web frontend
(web/ -- a standalone Next.js server, not served by this process; see
Documentation/MATCHING.md and the frontend-rewrite plan for why).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import get_app_config
from .middleware import RateLimitMiddleware
from .routes import export, health, match, opportunities, search, tags


def create_app() -> FastAPI:
    config = get_app_config()

    app = FastAPI(
        title="ISSR Funding Intelligence API",
        description="AI-Powered Funding Opportunity Discovery for ISSR",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Health is exempt so uptime checks can't be throttled out.
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=config.api_rate_limit_per_minute,
        exempt_paths={"/api/health"},
    )

    # CORS for separately hosted frontends. Origins come from config rather than
    # "*": a wildcard cannot be combined with credentialed requests, and the
    # bundled frontend is same-origin so it needs no exception at all.
    allow_credentials = "*" not in config.api_cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api_cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(
        opportunities.router, prefix="/api/opportunities", tags=["opportunities"]
    )
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    app.include_router(match.router, prefix="/api/match", tags=["match"])
    app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
    app.include_router(export.router, prefix="/api/export", tags=["export"])

    return app


app = create_app()
