---
id: 0037
title: Coerce non-UUID clinic_id before queue.enqueue (agent /api/run 500)
area: agent
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

`POST /api/run` (agent) 500'd when called with a non-UUID `clinic_id`.
`create_run` coerced the value to a valid `clinics(id)` UUID internally, but
`queue.enqueue` received the RAW value and inserted it into `jobs.clinic_id`
(a UUID column) → `asyncpg.DataError: invalid UUID 'demo-clinic-0001'`.

Found driving the canonical Python-agent path from the browser (ticket 0025
proxy): the web session's demo `clinic_id` ("demo-clinic-0001") flowed through
the proxy to the agent and blew up the enqueue.

## Acceptance criteria

- [x] `clinic_id` coerced to a valid UUID ONCE in `post_run`, before both
      `create_run` and `queue.enqueue` (made `coerce_clinic_id` public in
      persist.py).
- [x] Browser upload → proxy → enqueue → worker now completes:
      EXECUTE→READ-WEB→PERSIST→VERIFY→ACTION, status `submitted`, job `done`
      with `pdf_bytes` cleared — verified against real Postgres.
- [x] ruff clean; 27 agent tests pass.

## Files / surfaces

- `apps/agent/main.py` (coerce once in post_run)
- `apps/agent/src/persist.py` (`coerce_clinic_id` made public)

## Log

- 2026-06-03 — Surfaced by the end-to-end browser test of the agent run path.
  `queue.enqueue` got the un-coerced demo clinic slug. Fixed by coercing in
  `post_run` and sharing `coerce_clinic_id`. Re-ran from the browser: full
  5-verb pipeline streamed through the web-proxied SSE and persisted durably.

## Outcome

The agent run path (browser → web proxy → Python agent → durable worker → SSE)
now works end-to-end. A non-UUID clinic id (demo session) no longer 500s the
enqueue; it maps to the backfill clinic, consistent with create_run.
