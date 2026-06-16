"""FastAPI entrypoint for the Authmatic agent service.

Endpoints:
  POST /api/run            — upload a prescription PDF, get a run_id
  GET  /api/run/{run_id}   — full run detail (for /run/:id audit page)
  GET  /api/stream/{run_id}— SSE stream of agent events (for the live UI)
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from src import queue
from src.auth import require_service_token
from src.logging import setup_logging
from src.persist import (
    coerce_clinic_id,
    create_run,
    fetch_run_detail,
    fetch_run_status,
    poll_events_since,
)
from src.ratelimit import rate_limit_run
from src.upload import read_pdf_upload

load_dotenv()
setup_logging()  # JSON structured logging to stdout (ticket 0011)

# Terminal run states — the SSE tailer stops once a run reaches one.
_TERMINAL = {"submitted", "approved", "denied", "error"}
# How often the SSE handler polls durable agent_events for new steps (ticket
# 0028 — no in-process queue; any instance can tail a run another host runs).
_SSE_POLL_SECONDS = 0.5


async def _init_conn(conn: asyncpg.Connection) -> None:
    # Round-trip JSONB columns as Python dicts/lists, not raw JSON strings.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on unsafe prod config (ticket 0019) before opening the pool.
    from src.settings import assert_safe_for_production, get_settings

    assert_safe_for_production(get_settings())
    app.state.pool = await asyncpg.create_pool(
        os.environ["INSFORGE_DB_URL"], init=_init_conn,
    )
    yield
    await app.state.pool.close()


app = FastAPI(title="Authmatic Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("WEB_BASE_URL", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_id(request: Request, call_next):
    """Bind the inbound X-Request-ID to the log context + echo it (ticket 0021),
    so a run correlates across web → agent → tool calls."""
    from src.logging import request_id_var

    rid = request.headers.get("x-request-id") or ""
    token = request_id_var.set(rid or None)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    if rid:
        response.headers["x-request-id"] = rid
    return response


@app.post(
    "/api/run",
    dependencies=[Depends(require_service_token), Depends(rate_limit_run)],
)
async def post_run(
    request: Request,
    pdf: UploadFile = File(...),
    clinic_id: str = Form(default="unknown"),
) -> dict[str, str]:
    # Hardened intake (ticket 0013): size cap + magic-byte validation +
    # sanitized storage key. The client content_type header is advisory only;
    # read_pdf_upload confirms the real bytes.
    pdf_bytes = await read_pdf_upload(pdf, request.headers.get("content-length"))
    # Coerce once so BOTH the run row and the queue job get a valid clinics(id)
    # UUID (the jobs.clinic_id column is UUID; a demo slug would 500 the insert).
    clinic = coerce_clinic_id(clinic_id)
    filename = pdf.filename or "rx.pdf"
    run_id = await create_run(app.state.pool, pdf_bytes, filename, clinic_id=clinic)

    # Durable queue (ticket 0027): enqueue and return immediately. A separate
    # worker process (src/worker.py) runs the agent to completion — no
    # post-response `create_task` that a frozen instance would drop.
    await queue.enqueue(app.state.pool, run_id, pdf_bytes, filename, clinic_id=clinic)
    return {"run_id": run_id, "status": "queued"}


@app.get("/api/run/{run_id}", dependencies=[Depends(require_service_token)])
async def get_run(run_id: str) -> dict:
    try:
        UUID(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid run_id") from e
    detail = await fetch_run_detail(app.state.pool, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return detail


@app.get("/api/stream/{run_id}", dependencies=[Depends(require_service_token)])
async def stream(run_id: str) -> EventSourceResponse:
    # Durable SSE (ticket 0028): there is no in-process queue. We tail the
    # `agent_events` table — replaying any steps already written, then polling
    # for new ones — until the run reaches a terminal status. This works no
    # matter which host (API or worker) is executing the run, so a second
    # instance never needs to start a duplicate pipeline.
    async def gen():
        last_step = 0
        while True:
            events = await poll_events_since(app.state.pool, run_id, after_step=last_step)
            for ev in events:
                last_step = max(last_step, ev["step_no"])
                yield {"data": json.dumps(ev)}

            status = await fetch_run_status(app.state.pool, run_id)
            if status is None:
                yield {"data": json.dumps({"error": "run not found"})}
                break
            if status in _TERMINAL and not events:
                # Terminal and we've drained all steps.
                yield {"data": json.dumps({"done": True, "status": status})}
                break
            await asyncio.sleep(_SSE_POLL_SECONDS)

    return EventSourceResponse(gen())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def ready() -> dict:
    """Readiness probe (ticket 0015): 200 only if the DB pool answers."""
    try:
        async with app.state.pool.acquire() as conn:
            db_ok = (await conn.fetchval("SELECT 1")) == 1
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    if not db_ok:
        raise HTTPException(status_code=503, detail={"status": status, "deps": {"db": "down"}})
    return {"status": status, "deps": {"db": "ok"}}


@app.get("/api/smoke", dependencies=[Depends(require_service_token)])
async def smoke() -> dict:
    """Hello-world each sponsor. Used by scripts/smoke.sh. Admin/service-only."""
    from src.tools import execute, read_web, verify

    results = {}
    results["rtrvr"] = await read_web.ping()
    results["daytona"] = await execute.ping()
    results["opsera"] = await verify.ping()
    async with app.state.pool.acquire() as conn:
        results["insforge"] = {"ok": (await conn.fetchval("SELECT 1")) == 1}
    return results
