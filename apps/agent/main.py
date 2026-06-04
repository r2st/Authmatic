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

from src.auth import require_service_token
from src.loop import run_agent
from src.persist import (
    create_run,
    fetch_run_detail,
    poll_events_since,
)
from src.upload import read_pdf_upload

load_dotenv()

# In-process queue: run_id → asyncio.Queue of events for SSE fan-out.
# Single-process demo; production would use Redis pub/sub.
_RUN_QUEUES: dict[str, asyncio.Queue] = {}


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


@app.post("/api/run", dependencies=[Depends(require_service_token)])
async def post_run(
    request: Request,
    pdf: UploadFile = File(...),
    clinic_id: str = Form(default="unknown"),
) -> dict[str, str]:
    # Hardened intake (ticket 0013): size cap + magic-byte validation +
    # sanitized storage key. The client content_type header is advisory only;
    # read_pdf_upload confirms the real bytes.
    pdf_bytes = await read_pdf_upload(pdf, request.headers.get("content-length"))
    run_id = await create_run(
        app.state.pool, pdf_bytes, pdf.filename or "rx.pdf", clinic_id=clinic_id
    )

    queue: asyncio.Queue = asyncio.Queue()
    _RUN_QUEUES[run_id] = queue

    async def _on_event(event: dict) -> None:
        await queue.put(event)

    async def _run_in_background() -> None:
        try:
            await run_agent(
                pool=app.state.pool,
                run_id=run_id,
                pdf_bytes=pdf_bytes,
                on_event=_on_event,
            )
        finally:
            await queue.put({"done": True})
            # Keep queue around briefly so late subscribers still see "done".
            await asyncio.sleep(30)
            _RUN_QUEUES.pop(run_id, None)

    asyncio.create_task(_run_in_background())
    return {"run_id": run_id}


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
    queue = _RUN_QUEUES.get(run_id)

    async def gen():
        if queue is not None:
            # Live run — drain the in-process queue.
            while True:
                ev = await queue.get()
                yield {"data": json.dumps(ev)}
                if ev.get("done"):
                    break
        else:
            # Late subscriber — replay from the DB, then end.
            for ev in await poll_events_since(app.state.pool, run_id, after_step=-1):
                yield {"data": json.dumps(ev)}
            yield {"data": json.dumps({"done": True})}

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
