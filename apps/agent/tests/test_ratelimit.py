"""Agent rate-limit tests (ticket 0012): 11th /api/run in a minute → 429."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import ratelimit  # noqa: E402


def setup_function():
    ratelimit._hits.clear()


def test_allows_up_to_limit_then_429():
    auth = "Bearer tok-A"
    for _ in range(ratelimit._MAX_PER_WINDOW):
        ratelimit.rate_limit_run(auth)  # 10 allowed
    with pytest.raises(HTTPException) as e:
        ratelimit.rate_limit_run(auth)  # 11th
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers


def test_buckets_are_per_token():
    ratelimit.rate_limit_run("Bearer tok-A")
    # A different token has its own budget.
    for _ in range(ratelimit._MAX_PER_WINDOW):
        ratelimit.rate_limit_run("Bearer tok-B")
    with pytest.raises(HTTPException):
        ratelimit.rate_limit_run("Bearer tok-B")
