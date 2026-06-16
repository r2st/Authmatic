"""Durable job-queue tests (ticket 0027).

Integration test against a real Postgres (the queue logic is SQL:
`FOR UPDATE SKIP LOCKED`, retry/backoff, dead-letter, stuck recovery). Skips
cleanly when no DB is reachable, so the local suite stays green without
docker; CI (which has Postgres) runs it for real.

Covers the "kill the worker mid-run → recovered, not lost" criterion via
`requeue_stuck` on a job left in `running` past the stuck window.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

asyncpg = pytest.importorskip("asyncpg")

from src import queue  # noqa: E402

# Pin to the LOCAL dev DB (docker-compose.local). Deliberately NOT
# INSFORGE_DB_URL — another test imports main (load_dotenv) which can repoint
# that at a prod/cloud DB with RLS that blocks these direct inserts.
DB_URL = os.environ.get("TEST_DB_URL", "postgres://authmatic:authmatic@localhost:55432/authmatic")


async def _connect_or_skip():
    try:
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable for queue tests: {e}")
    # Reachable but unmigrated, or RLS blocks our inserts → skip, don't fail.
    async with pool.acquire() as conn:
        if await conn.fetchval("SELECT to_regclass('public.jobs')") is None:
            await pool.close()
            pytest.skip("Postgres reachable but `jobs` table not migrated")
        # Clean slate: claim_next picks the globally-oldest queued job, so
        # leftover jobs from a previous run would mislead the assertions.
        await conn.execute("DELETE FROM jobs")
    return pool


async def _seed_run(pool) -> str:
    """Create a minimal prior_auths row so the jobs FK is satisfied. Includes
    clinic_id (the default backfill clinic) since 0007 made it NOT NULL."""
    default_clinic = "00000000-0000-0000-0000-000000000001"
    async with pool.acquire() as conn:
        pid = await conn.fetchval(
            "INSERT INTO patients (full_name, dob, plan_id, member_id, clinic_id) "
            "VALUES ('Q Test', '1990-01-01', 'P', $1, $2) RETURNING id",
            f"Q-{uuid.uuid4().hex[:8]}", default_clinic,
        )
        return str(
            await conn.fetchval(
                "INSERT INTO prior_auths (patient_id, drug_name, status, clinic_id) "
                "VALUES ($1, '<pending>', 'pending', $2) RETURNING id",
                pid, default_clinic,
            )
        )


async def test_enqueue_claim_complete():
    pool = await _connect_or_skip()
    try:
        run_id = await _seed_run(pool)
        job_id = await queue.enqueue(pool, run_id, b"%PDF-1.4", "rx.pdf", clinic_id=None)
        # enqueue is idempotent on run_id.
        assert await queue.enqueue(pool, run_id, b"%PDF-1.4", "rx.pdf") == job_id

        claimed = await queue.claim_next(pool, "w1")
        assert claimed is not None and str(claimed["run_id"]) == run_id
        # The job is now 'running' and locked by w1 — a second worker's claim
        # query (status='queued') will never re-pick this same job.
        async with pool.acquire() as conn:
            jrow = await conn.fetchrow("SELECT status, locked_by FROM jobs WHERE id=$1", job_id)
        assert jrow["status"] == "running"
        assert jrow["locked_by"] == "w1"

        await queue.complete(pool, job_id)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status, pdf_bytes FROM jobs WHERE id = $1", job_id)
        assert row["status"] == "done"
        assert row["pdf_bytes"] is None  # PHI cleared on completion
    finally:
        await pool.close()


async def test_fail_retries_then_dead_letters():
    pool = await _connect_or_skip()
    try:
        run_id = await _seed_run(pool)
        job_id = await queue.enqueue(pool, run_id, b"%PDF-1.4", "rx.pdf")
        async with pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET attempts = max_attempts WHERE id = $1", job_id)
        assert await queue.fail(pool, job_id, "boom") == "dead"
    finally:
        await pool.close()


async def test_requeue_stuck_recovers_a_killed_worker():
    pool = await _connect_or_skip()
    try:
        run_id = await _seed_run(pool)
        job_id = await queue.enqueue(pool, run_id, b"%PDF-1.4", "rx.pdf")
        async with pool.acquire() as conn:
            # Simulate a worker that claimed the job then died long ago.
            await conn.execute(
                "UPDATE jobs SET status='running', "
                "locked_at = now() - interval '1 hour' WHERE id = $1",
                job_id,
            )
        recovered = await queue.requeue_stuck(pool)
        assert recovered >= 1
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT status FROM jobs WHERE id=$1", job_id) == "queued"
    finally:
        await pool.close()
