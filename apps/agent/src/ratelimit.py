"""In-process sliding-window rate limiter for the agent API (ticket 0012).

Limits `POST /api/run` to 10 requests / token / minute. Per-process (a
horizontally-scaled deploy needs Redis); documented as the upgrade path.
Used as a FastAPI dependency alongside the service-token check.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException

_WINDOW_SECONDS = 60
_MAX_PER_WINDOW = 10
_hits: dict[str, deque[float]] = defaultdict(deque)


def _bucket_key(authorization: str | None) -> str:
    # Bucket by the bearer token (service identity). Falls back to a shared
    # key when absent so unauthenticated floods are still bounded.
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :].strip()[:32]
    return "_anon"


def rate_limit_run(authorization: str | None = Header(default=None)) -> None:
    key = _bucket_key(authorization)
    now = time.monotonic()
    dq = _hits[key]
    cutoff = now - _WINDOW_SECONDS
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if len(dq) >= _MAX_PER_WINDOW:
        retry = int(dq[0] + _WINDOW_SECONDS - now) + 1
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, retry))},
        )
    dq.append(now)
