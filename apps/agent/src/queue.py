"""Durable job queue operations on the `jobs` table (ticket 0027).

At-least-once delivery with `FOR UPDATE SKIP LOCKED` claiming, bounded
retries with backoff, dead-lettering, and stuck-run recovery. Pure DB
functions — the worker (worker.py) orchestrates them; the API enqueues.

Why Postgres-as-a-queue (vs Redis/BullMQ): InsForge already gives us a
transactional Postgres, the volume is low, and `SKIP LOCKED` is a robust,
well-trodden queue primitive. ADR 0014 records the choice. Swap the
claim/complete functions for a managed queue later without touching callers.
"""

from __future__ import annotations

import asyncpg

# A run is considered stuck if claimed but not finished within this window;
# it is returned to the queue for another worker (crash recovery).
STUCK_AFTER_SECONDS = 300
# Exponential-ish backoff between retries.
RETRY_BACKOFF_SECONDS = 30


async def enqueue(
    pool: asyncpg.Pool,
    run_id: str,
    pdf_bytes: bytes,
    filename: str,
    clinic_id: str | None = None,
) -> str:
    """Insert a queued job for an already-created run. Idempotent on run_id
    (UNIQUE) — a redelivered enqueue does not create a second job."""
    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """
            INSERT INTO jobs (run_id, clinic_id, pdf_bytes, filename, status)
            VALUES ($1, $2, $3, $4, 'queued')
            ON CONFLICT (run_id) DO NOTHING
            RETURNING id
            """,
            run_id, clinic_id, pdf_bytes, filename,
        )
        if job_id is None:  # already enqueued
            job_id = await conn.fetchval("SELECT id FROM jobs WHERE run_id = $1", run_id)
    return str(job_id)


async def claim_next(pool: asyncpg.Pool, worker_id: str) -> asyncpg.Record | None:
    """Atomically claim the next runnable job. Returns the job row (incl.
    pdf_bytes) or None. Uses SKIP LOCKED so concurrent workers never collide."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, run_id, clinic_id, pdf_bytes, filename, attempts, max_attempts
                FROM jobs
                WHERE status = 'queued' AND run_after <= now()
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            if row is None:
                return None
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'running', attempts = attempts + 1,
                    locked_at = now(), locked_by = $2
                WHERE id = $1
                """,
                row["id"], worker_id,
            )
    return row


async def complete(pool: asyncpg.Pool, job_id: str) -> None:
    """Mark done and drop the transient PDF bytes (PHI hygiene)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status = 'done', pdf_bytes = NULL, locked_at = NULL WHERE id = $1",
            job_id,
        )


async def fail(pool: asyncpg.Pool, job_id: str, error: str) -> str:
    """Record a failure. Retry with backoff until max_attempts, then dead-letter.
    Returns the new status ('queued' for retry, 'dead' for dead-letter)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT attempts, max_attempts FROM jobs WHERE id = $1", job_id)
        if row and row["attempts"] >= row["max_attempts"]:
            await conn.execute(
                "UPDATE jobs SET status = 'dead', last_error = $2, "
                "pdf_bytes = NULL, locked_at = NULL WHERE id = $1",
                job_id, error[:1000],
            )
            return "dead"
        # RETRY_BACKOFF_SECONDS is a trusted int module constant, not user
        # input — the f-string is safe (S608 false positive).
        await conn.execute(
            f"""
            UPDATE jobs
            SET status = 'queued', last_error = $2, locked_at = NULL,
                run_after = now() + interval '{RETRY_BACKOFF_SECONDS} seconds'
            WHERE id = $1
            """,  # noqa: S608
            job_id, error[:1000],
        )
        return "queued"


async def requeue_stuck(pool: asyncpg.Pool) -> int:
    """Return runs claimed but not finished within STUCK_AFTER_SECONDS to the
    queue (a worker died mid-run). Returns the count recovered."""
    async with pool.acquire() as conn:
        # STUCK_AFTER_SECONDS is a trusted int constant (S608 false positive).
        result = await conn.execute(
            f"""
            UPDATE jobs
            SET status = 'queued', locked_at = NULL, locked_by = NULL
            WHERE status = 'running'
              AND locked_at < now() - interval '{STUCK_AFTER_SECONDS} seconds'
            """  # noqa: S608
        )
    # asyncpg returns e.g. "UPDATE 3"
    return int(result.split()[-1]) if result else 0
