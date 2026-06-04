---
id: 0027
title: Run agent jobs on a durable queue, not fire-and-forget
area: multi
priority: P0
status: inbox
owner:
created: 2026-06-03
started:
closed:
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

- [ ] Agent runs execute on a durable queue (InsForge schedules/edge functions, a worker dyno, BullMQ+Redis, or a managed queue) — chosen and ADR'd
- [ ] `POST /api/run` enqueues a job and returns immediately with `run_id` + `status: queued`; it does not depend on post-response execution
- [ ] A worker (separate process / dyno / function with a guaranteed execution model) consumes the queue and runs the agent
- [ ] Jobs are at-least-once with idempotency ([[0017]]) so a redelivered job doesn't double-file
- [ ] Stuck-run detection: a run in `running`/`queued` past a timeout is marked `failed` and (optionally) retried with backoff
- [ ] Dead-letter handling for jobs that fail repeatedly; surfaced to observability ([[0011]])
- [ ] Test: kill the worker mid-run; the job is retried/recovered, not lost

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
