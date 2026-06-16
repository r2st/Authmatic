"""Async status poller — periodically checks payer for PA status updates.

Reads rows from prior_auths where next_poll_at <= now(), calls the
payer adapter's check_status, and writes the result back. Backs off
exponentially on each poll and stops after a configurable max count.

Designed to run as a long-lived asyncio task inside the worker process.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from .base import PayerAdapter, PayerError, PayerStatus

_logger = logging.getLogger("authmatic.payer.poller")

# Polling schedule: each poll pushes the next further out.
# poll_count → next_poll delay in minutes.
_BACKOFF_MINUTES = [5, 15, 30, 60, 120, 240, 480, 1440]  # caps at 24h
MAX_POLL_COUNT = 50  # stop polling after this many attempts


def _next_delay_minutes(poll_count: int) -> int:
    idx = min(poll_count, len(_BACKOFF_MINUTES) - 1)
    return _BACKOFF_MINUTES[idx]


# Terminal statuses — once reached, no further polling.
_TERMINAL = {PayerStatus.APPROVED, PayerStatus.DENIED, PayerStatus.CANCELLED}


async def poll_once(
    pool: asyncpg.Pool,
    adapter: PayerAdapter,
    batch_size: int = 20,
) -> int:
    """Poll up to `batch_size` PAs whose next_poll_at has arrived.

    Returns the number of rows successfully polled (for metrics).
    """
    now = datetime.now(timezone.utc)
    polled = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, external_reference_id, poll_count
            FROM prior_auths
            WHERE external_reference_id IS NOT NULL
              AND payer_status NOT IN ('approved', 'denied', 'cancelled')
              AND next_poll_at IS NOT NULL
              AND next_poll_at <= $1
              AND (poll_count < $2 OR poll_count IS NULL)
            ORDER BY next_poll_at ASC
            LIMIT $3
            """,
            now,
            MAX_POLL_COUNT,
            batch_size,
        )

    for row in rows:
        pa_id = str(row["id"])
        ext_ref = row["external_reference_id"]
        count = row["poll_count"] or 0

        try:
            result = await adapter.check_status(ext_ref)
        except PayerError as e:
            _logger.warning(
                "poller.check_failed",
                extra={"pa_id": pa_id, "ext_ref": ext_ref, "error": str(e)},
            )
            # On transient error, schedule the next poll anyway.
            await _update_poll_schedule(pool, pa_id, count, None, None)
            continue
        except Exception:
            _logger.exception("poller.unexpected_error", extra={"pa_id": pa_id})
            await _update_poll_schedule(pool, pa_id, count, None, None)
            continue

        status = result.status
        denial = result.denial_reason

        if status in _TERMINAL:
            # Final status reached — clear next_poll_at so we stop.
            await _finalize(pool, pa_id, status, denial)
            _logger.info(
                "poller.terminal",
                extra={"pa_id": pa_id, "status": status.value},
            )
        else:
            await _update_poll_schedule(pool, pa_id, count, status, denial)

        polled += 1

    return polled


async def _update_poll_schedule(
    pool: asyncpg.Pool,
    pa_id: str,
    current_count: int,
    status: PayerStatus | None,
    denial_reason: str | None,
) -> None:
    """Bump poll_count, compute next_poll_at with backoff."""
    new_count = current_count + 1
    delay = _next_delay_minutes(new_count)
    next_poll = datetime.now(timezone.utc) + timedelta(minutes=delay)

    async with pool.acquire() as conn:
        if status is not None:
            await conn.execute(
                """
                UPDATE prior_auths SET
                  payer_status = $2,
                  denial_reason = COALESCE($3, denial_reason),
                  poll_count = $4,
                  last_polled_at = now(),
                  next_poll_at = $5
                WHERE id = $1
                """,
                pa_id,
                status.value,
                denial_reason,
                new_count,
                next_poll,
            )
        else:
            # Error path — just bump the schedule.
            await conn.execute(
                """
                UPDATE prior_auths SET
                  poll_count = $2,
                  last_polled_at = now(),
                  next_poll_at = $3
                WHERE id = $1
                """,
                pa_id,
                new_count,
                next_poll,
            )


async def _finalize(
    pool: asyncpg.Pool,
    pa_id: str,
    status: PayerStatus,
    denial_reason: str | None,
) -> None:
    """Write terminal status and stop polling."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE prior_auths SET
              payer_status = $2,
              denial_reason = COALESCE($3, denial_reason),
              last_polled_at = now(),
              next_poll_at = NULL
            WHERE id = $1
            """,
            pa_id,
            status.value,
            denial_reason,
        )


async def run_poller_loop(
    pool: asyncpg.Pool,
    adapter: PayerAdapter,
    interval_seconds: float = 60,
    batch_size: int = 20,
) -> None:
    """Long-lived loop: poll eligible PAs every `interval_seconds`.

    Designed to run as an asyncio.create_task in the worker. Exits
    cleanly on cancellation.
    """
    _logger.info("poller.started", extra={"interval_s": interval_seconds})
    while True:
        try:
            count = await poll_once(pool, adapter, batch_size)
            if count:
                _logger.info("poller.batch_done", extra={"polled": count})
        except asyncpg.PostgresError as e:
            _logger.error("poller.db_error", extra={"error": str(e)})
        except asyncio.CancelledError:
            _logger.info("poller.stopped")
            raise
        except Exception:
            _logger.exception("poller.loop_error")

        await asyncio.sleep(interval_seconds)
