"""
Custom ASGI middleware for the API.

Deliberately dependency-free: a single-instance prototype at ISSR scale does not
justify pulling in slowapi/redis, and an in-process limiter keeps `pip install`
unchanged for anyone picking this up. The trade-off is that limits are per
worker process, not global — if this is ever deployed behind multiple workers or
replicas, swap this for a shared-store limiter.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60

# Stop tracking clients that have been silent for this long, so the bookkeeping
# doesn't grow without bound in a long-running process.
IDLE_EVICTION_SECONDS = 300


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Fixed-capacity sliding-window rate limit, keyed by client IP.

    Read-only endpoints over public funding data don't need per-user quotas —
    this exists to stop a single misbehaving client (or a scraper) from
    saturating the server, which the API previously had no defence against.
    """

    def __init__(self, app, requests_per_minute: int = 120, exempt_paths=None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exempt_paths = set(exempt_paths or [])
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_evicted = time.monotonic()

    def _client_key(self, request: Request) -> str:
        # X-Forwarded-For is only meaningful behind a trusted proxy that sets
        # it; direct clients can spoof it. Prefer the socket peer and fall back
        # to the header so the limiter still distinguishes clients when the app
        # is proxied.
        if request.client and request.client.host:
            return request.client.host
        forwarded = request.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() or "unknown"

    def _evict_idle(self, now: float) -> None:
        if now - self._last_evicted < IDLE_EVICTION_SECONDS:
            return
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] > IDLE_EVICTION_SECONDS
        ]
        for key in stale:
            del self._hits[key]
        self._last_evicted = now

    def _is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._evict_idle(now)
            hits = self._hits[key]
            cutoff = now - WINDOW_SECONDS
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.requests_per_minute:
                return False
            hits.append(now)
            return True

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt_paths or self.requests_per_minute <= 0:
            return await call_next(request)

        key = self._client_key(request)
        if not self._is_allowed(key):
            logger.warning("Rate limit exceeded for %s on %s", key, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded ({self.requests_per_minute} requests "
                        f"per {WINDOW_SECONDS}s). Please retry shortly."
                    )
                },
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        return await call_next(request)
