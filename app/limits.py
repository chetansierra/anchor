"""Public-demo guardrails for the open, keyless /chat endpoint.

The demo calls a paid LLM with no login, so two things protect the bill:
  - a per-IP rate limit (sliding 60s window, in-memory), and
  - a hard daily $ ceiling, enforced by summing today's recorded trace costs
    (Day 4) so it survives restarts.

An optional X-API-Key gate is the seam that makes per-client keys / multi-tenant
a small step later; unset by default (open demo). All three are pure, testable
pieces — `enforce_demo_limits` raises HTTPException; the caller just calls it.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException

from .config import Settings
from .traces import TraceStore


class RateLimiter:
    """In-memory per-key sliding-window limiter. Fine for a single-process demo;
    swap for Redis if this ever needs to span instances."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > 60.0:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        return True


def enforce_demo_limits(
    *,
    ip: str,
    api_key: str | None,
    settings: Settings,
    limiter: RateLimiter,
    store: TraceStore,
) -> None:
    """Raise HTTPException if a request must be rejected; return None to proceed."""
    if settings.demo_api_key and api_key != settings.demo_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    if not limiter.allow(ip):
        raise HTTPException(
            status_code=429,
            detail="You're sending requests a bit fast — please wait a moment and try again.",
            headers={"Retry-After": "30"},
        )

    if store.cost_today() >= settings.daily_cost_ceiling_usd:
        raise HTTPException(
            status_code=429,
            detail="The demo's daily budget has been reached — please try again tomorrow.",
        )
