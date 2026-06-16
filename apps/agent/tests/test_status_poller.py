"""Tests for the status poller — exponential backoff, terminal detection.

Unit-level: mocks asyncpg and the payer adapter to verify polling logic
without touching a real database or network.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.payer.base import PayerError, PayerStatus, StatusResult  # noqa: E402
from src.payer.status_poller import (  # noqa: E402
    MAX_POLL_COUNT,
    _next_delay_minutes,
    poll_once,
)


# ── Backoff schedule ─────────────────────────────────────────────────────


def test_backoff_starts_at_5_minutes():
    assert _next_delay_minutes(0) == 5


def test_backoff_increases():
    delays = [_next_delay_minutes(i) for i in range(8)]
    assert delays == [5, 15, 30, 60, 120, 240, 480, 1440]


def test_backoff_caps_at_24h():
    assert _next_delay_minutes(100) == 1440
    assert _next_delay_minutes(MAX_POLL_COUNT) == 1440


# ── poll_once ────────────────────────────────────────────────────────────


def _mock_pool(rows):
    """Build a mock asyncpg pool that returns `rows` from fetch and executes."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock()

    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


async def test_poll_once_no_rows():
    pool, _ = _mock_pool([])
    adapter = AsyncMock()
    count = await poll_once(pool, adapter, batch_size=10)
    assert count == 0
    adapter.check_status.assert_not_called()


async def test_poll_once_terminal_status():
    """When the payer returns APPROVED, the poller finalizes (sets next_poll_at=NULL)."""
    rows = [
        {"id": "pa-1", "external_reference_id": "EXT-1", "poll_count": 3},
    ]
    pool, conn = _mock_pool(rows)

    adapter = AsyncMock()
    adapter.check_status = AsyncMock(
        return_value=StatusResult(
            external_reference_id="EXT-1",
            status=PayerStatus.APPROVED,
        )
    )

    count = await poll_once(pool, adapter, batch_size=10)
    assert count == 1

    # Should have called execute to finalize (NULL next_poll_at).
    calls = conn.execute.call_args_list
    assert any("next_poll_at = NULL" in str(c) for c in calls)


async def test_poll_once_non_terminal_bumps_schedule():
    """When payer returns PENDING, the poller bumps poll_count and schedules next."""
    rows = [
        {"id": "pa-2", "external_reference_id": "EXT-2", "poll_count": 1},
    ]
    pool, conn = _mock_pool(rows)

    adapter = AsyncMock()
    adapter.check_status = AsyncMock(
        return_value=StatusResult(
            external_reference_id="EXT-2",
            status=PayerStatus.PENDING,
        )
    )

    count = await poll_once(pool, adapter, batch_size=10)
    assert count == 1

    # Should have called execute to update schedule (NOT finalize).
    calls = conn.execute.call_args_list
    assert not any("next_poll_at = NULL" in str(c) for c in calls)


async def test_poll_once_handles_payer_error():
    """On PayerError, the poller still bumps the schedule (does not crash)."""
    rows = [
        {"id": "pa-3", "external_reference_id": "EXT-3", "poll_count": 0},
    ]
    pool, conn = _mock_pool(rows)

    adapter = AsyncMock()
    adapter.check_status = AsyncMock(
        side_effect=PayerError("Timeout", retryable=True)
    )

    # Should not raise.
    count = await poll_once(pool, adapter, batch_size=10)
    assert count == 0  # error path doesn't count as "polled"

    # But it should have scheduled the next poll.
    assert conn.execute.called
