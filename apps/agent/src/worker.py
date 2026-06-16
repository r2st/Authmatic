"""Agent run worker (ticket 0027). Run as a SEPARATE process from the API:

    python -m src.worker

Guaranteed execution model: a long-running worker dyno (Render background
worker) — NOT post-response `create_task`, which a frozen serverless instance
drops. The worker claims jobs from the `jobs` table, runs the agent to
completion, and marks them done/failed-with-retry/dead. On boot and
periodically it recovers stuck runs (a worker that died mid-run).

SSE/run state is durable in `prior_auths`/`agent_events` (the agent persists
each step), so the API can stream a run that a worker — possibly on another
host — is executing (ticket 0028).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket

import asyncpg
from dotenv import load_dotenv

from . import queue
from .logging import setup_logging
from .loop import run_agent
from .persist import update_status

load_dotenv()
setup_logging()
_log = logging.getLogger("authmatic.agent.worker")

POLL_INTERVAL_SECONDS = 2
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def _run_job(pool: asyncpg.Pool, job: asyncpg.Record) -> None:
    run_id = str(job["run_id"])
    _log.info(
        "job.start",
        extra={"run_id": run_id, "worker": WORKER_ID, "attempts": job["attempts"]},
    )

    async def _noop_event(_event: dict) -> None:
        # Events are durable in agent_events (persist.append_event); the API
        # tails them from the DB. The worker doesn't need an in-process sink.
        return None

    try:
        await run_agent(
            pool=pool,
            run_id=run_id,
            pdf_bytes=bytes(job["pdf_bytes"]),
            on_event=_noop_event,
        )
        await queue.complete(pool, str(job["id"]))
        _log.info("job.done", extra={"run_id": run_id})
    except Exception as e:  # noqa: BLE001
        status = await queue.fail(pool, str(job["id"]), str(e))
        await update_status(pool=pool, pa_id=run_id, status="error")
        _log.error("job.failed", extra={"run_id": run_id, "outcome": status, "error": str(e)})


async def main() -> None:
    pool = await asyncpg.create_pool(os.environ["INSFORGE_DB_URL"], init=_init_conn)
    _log.info("worker.boot", extra={"worker": WORKER_ID})
    recovered = await queue.requeue_stuck(pool)
    if recovered:
        _log.info("worker.recovered_stuck", extra={"count": recovered})

    idle_ticks = 0
    try:
        while True:
            job = await queue.claim_next(pool, WORKER_ID)
            if job is None:
                idle_ticks += 1
                # Periodically sweep for stuck runs while idle.
                if idle_ticks % 30 == 0:
                    await queue.requeue_stuck(pool)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            idle_ticks = 0
            await _run_job(pool, job)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
