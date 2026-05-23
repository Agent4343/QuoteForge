"""Minimal in-memory sliding-window rate limiter (§16).

Sufficient for a single-instance v1 deployment. If QuoteForge ever runs more
than one replica, move this to a shared store (e.g. Postgres or Redis).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def _check(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    bucket = _BUCKETS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )
    bucket.append(now)


def rate_limit(scope: str, limit: int, window_seconds: int):
    """Build a FastAPI dependency limiting requests per client IP for a scope."""

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        _check(f"{scope}:{client}", limit, window_seconds)

    return dependency


def reset() -> None:
    """Clear all buckets (used by tests)."""
    _BUCKETS.clear()
