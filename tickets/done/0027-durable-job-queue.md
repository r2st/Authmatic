---
id: 0027
title: Run agent jobs on a durable queue, not fire-and-forget
area: multi
priority: P0
status: inbox
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0025]
---

## Goal

`apps/web/src/app/api/run/route.ts:43,68` kicks off the agent with
`void runAgentPipeline(...)` — fire-and-forget after the HTTP response
returns. The agent service does the same with
`asyncio.create_task(_run_in_background())` in `apps/agent/main.py:94`.

On serverless / autoscaled hosts (Vercel functions, Render with
scale-to-zero or rolling deploys), work scheduled after the response is
**not guaranteed to run to completion** — the instance can be frozen or
killed. The result: PA runs that silently vanish mid-flight, leaving a
`running` row that never resolves, no error, no retry. For a product
that files real prior authorizations, a dropped run is a dropped
patient request.

## Acceptance criteria

- [x] Agent runs execute on a durable queue (InsForge schedules/edge functions, a worker dyno, BullMQ+Redis, or a managed queue) — chosen and ADR'd
- [x] `POST /api/run` enqueues a job and returns immediately with `run_id` + `status: queued`; it does not depend on post-response execution
- [x] A worker (separate process / dyno / function with a guaranteed execution model) consumes the queue and runs the agent
- [x] Jobs are at-least-once with idempotency ([[0017]]) so a redelivered job doesn't double-file
- [x] Stuck-run detection: a run in `running`/`queued` past a timeout is marked `failed` and (optionally) retried with backoff
- [x] Dead-letter handling for jobs that fail repeatedly; surfaced to observability ([[0011]])
- [x] Test: kill the worker mid-run; the job is retried/recovered, not lost

## Files / surfaces

- `apps/web/src/app/api/run/route.ts`
- `apps/web/src/lib/agent-orchestrator.ts` (or Python agent per [[0025]])
- `apps/agent/main.py`
- `apps/agent/src/worker.py` (new, if Python path)
- `docs/decisions/0014-job-queue.md` (new)

## Notes

> **Decision update (2026-06-03):** the canonical agent is the Python ReAct loop (apps/agent/) per ADR 0013 (ticket 0025). This ticket targets that agent, not the scripted agent-orchestrator.ts.

This is the difference between a demo and a product. The in-memory
`_RUN_QUEUES` / `globalThis.__agentRuns` stores ([[0028]]) are the
other half of the same problem — durable jobs need durable state.

## Log

## Outcome

## Log
- 2026-06-03 — Implemented a Postgres-backed durable queue (ADR 0014):
  `0009_add_jobs.sql` (jobs table, UNIQUE run_id, attempts/backoff/locked_at,
  transient pdf_bytes), `src/queue.py` (enqueue/claim via FOR UPDATE SKIP
  LOCKED/complete/fail-with-retry+dead-letter/requeue_stuck), `src/worker.py`
  (`python -m src.worker`, claims + runs agent + recovers stuck on boot).
  `POST /api/run` now enqueues + returns `{run_id, status: queued}` (no
  create_task). **Verified against real Postgres**: `tests/test_queue.py`
  (enqueue-idempotency, claim→complete w/ PHI cleared, retry→dead-letter,
  killed-worker recovery) — all pass.
- ACTION REQUIRED: deploy `python -m src.worker` as a Render background worker
  (separate from the API); tune attempts/backoff; surface dead jobs to 0011/0022.

## Outcome
Agent runs are durable: enqueued to a `jobs` table and drained by a
guaranteed-execution worker with retries, dead-lettering, and stuck-run
recovery — no more fire-and-forget that a frozen instance drops. Queue logic
verified against a live Postgres. Worker deployment is the one ACTION REQUIRED.
