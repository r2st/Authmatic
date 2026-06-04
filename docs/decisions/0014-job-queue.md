# ADR 0014 — Durable job queue for agent runs

- **Status:** accepted (queue + worker implemented + DB-tested; deploy of the worker dyno is ACTION REQUIRED)
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0027-durable-job-queue.md
- **Related:** [[0017]] idempotency, [[0028]] durable state/SSE, [[0025]] canonical agent

## Context

Both run paths were fire-and-forget: web `void runAgentPipeline(...)` and
agent `asyncio.create_task(...)` after the HTTP response. On serverless /
scale-to-zero / rolling deploys, post-response work is not guaranteed to run —
a run silently vanishes, leaving a `running` row that never resolves. For real
PA filing, a dropped run is a dropped patient request.

## Decision

**Postgres-as-a-queue** (the existing InsForge Postgres), not Redis/BullMQ or a
managed queue.

- `jobs` table (`db/migrations/0009_add_jobs.sql`): one row per run (`UNIQUE
  run_id` → idempotent enqueue, ties into [[0017]]), `status`
  queued→running→done/failed/dead, `attempts`/`max_attempts`, `run_after`
  (backoff), `locked_at`/`locked_by` (stuck detection). The uploaded PDF rides
  with the job (transient `pdf_bytes`, nulled at terminal state) so the worker
  is self-contained and survives an API restart.
- **Enqueue** (`POST /api/run`): insert the run + a job, return `{run_id,
  status: "queued"}` immediately. No post-response execution.
- **Worker** (`apps/agent/src/worker.py`, run as `python -m src.worker` on a
  dedicated dyno): claims jobs with `SELECT … FOR UPDATE SKIP LOCKED`, runs the
  agent to completion, marks done / retries with backoff / dead-letters after
  `max_attempts`. On boot + periodically it `requeue_stuck()`s runs whose
  worker died mid-flight.

**Why Postgres:** transactional, already provisioned, `SKIP LOCKED` is a proven
queue primitive, and the volume is low. Redis/BullMQ adds an operational
component for no benefit at this scale. The queue functions (`src/queue.py`)
are isolated, so swapping to a managed queue later doesn't touch callers.

## Verification

`apps/agent/tests/test_queue.py` runs against a real Postgres (skips when none
is reachable / unmigrated): enqueue-idempotency, claim→running→complete (with
PHI `pdf_bytes` cleared), retry→dead-letter at max attempts, and **killed-worker
recovery** (`requeue_stuck` returns a long-`running` job to `queued`). All pass
against the local docker DB.

## ACTION REQUIRED (human)

- Deploy `python -m src.worker` as a Render **background worker** (guaranteed
  execution model), separate from the API service.
- Set `max_attempts` / backoff / `STUCK_AFTER_SECONDS` per real sponsor latency.
- Surface `status='dead'` jobs to the observability stack ([[0011]]) /
  on-call ([[0022]]).

## Consequences

- A run can no longer vanish: it's a durable row a guaranteed-execution worker
  drains, with retries + stuck recovery.
- SSE no longer needs an in-process queue — the API tails durable
  `agent_events` ([[0028]]); any instance can stream a run another host runs.
- The PDF lives transiently in the queue row; cleared on completion (PHI
  hygiene, ADR 0008). A future optimization stores it in object storage and
  carries only the key.
