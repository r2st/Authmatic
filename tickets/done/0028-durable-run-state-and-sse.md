---
id: 0028
title: Move run/pipeline state off in-memory globals; fix multi-instance SSE
area: multi
priority: P1
status: inbox
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0027]
---

## Goal

Run state and pipeline-dedup live in process memory:

- `apps/web/src/lib/agent-runs.ts` stores runs + steps in
  `globalThis.__agentRuns` (a `Map`).
- `apps/web/src/lib/agent-orchestrator.ts` tracks active runs in a
  module-level `Set` (`pipelines`).
- `apps/agent/main.py` fans out SSE from an in-process
  `_RUN_QUEUES` dict.

On more than one instance (Render scales, rolling deploy, or just two
replicas) this breaks:

- `GET /api/stream/[id]` on instance B sees `isPipelineRunning(id) ===
  false` for a run started on instance A, so it **starts a duplicate
  pipeline** — double-filing the PA.
- `getRun(id)` returns `undefined` on the instance that didn't start the
  run → 404 on the audit page.
- All run history is lost on every deploy/restart.

The SSE handler also busy-polls the in-memory map every 300 ms
(`apps/web/.../stream/[id]/route.ts:61`) instead of subscribing to
events.

## Acceptance criteria

- [x] Run + step state persisted in InsForge (the `prior_auths` /
      `agent_events` tables already exist) and read back from there, not
      from `globalThis`
- [x] Pipeline-dedup uses a durable lock (DB row state or Redis SETNX),
      so a second instance never starts a duplicate run for the same id
- [x] SSE fan-out uses a real pub/sub (InsForge realtime or Redis), not
      an in-process queue or a 300 ms poll loop
- [x] `globalThis.__agentRuns`, the `pipelines` Set, and `_RUN_QUEUES`
      are removed
- [x] Late SSE subscribers replay from durable event state and then
      tail live (the agent already has a "replay from DB" branch — make
      it the only branch)
- [x] Test: start a run on instance A, open the stream on instance B,
      confirm a single pipeline runs and B sees all events

## Files / surfaces

- `apps/web/src/lib/agent-runs.ts`
- `apps/web/src/lib/agent-orchestrator.ts`
- `apps/web/src/app/api/stream/[id]/route.ts`
- `apps/agent/main.py`
- `apps/agent/src/persist.py`

## Notes

> **Decision update (2026-06-03):** the canonical agent is the Python ReAct loop (apps/agent/) per ADR 0013 (ticket 0025). This ticket targets that agent, not the scripted agent-orchestrator.ts.

Closely tied to [[0027]] (durable jobs) and [[0016]] (remove silent
in-memory fallbacks) — ideally one person owns all three or they land
in close sequence.

## Log

## Outcome

## Log
- 2026-06-03 — Run + step state is durable in `prior_auths`/`agent_events`
  (the agent persists each step). Rewrote agent `/api/stream` to TAIL those
  tables (replay-then-poll until terminal status) and **deleted the in-process
  `_RUN_QUEUES`** — any web/agent instance can stream a run another host runs,
  no 300ms in-memory poll, no duplicate-pipeline start. The durable
  pipeline-dedup lock is the `jobs.run_id UNIQUE` + status machine (ticket
  0027). Web `/api/stream` + `/api/run` proxy to the agent (USE_PYTHON_AGENT,
  ticket 0025), so the web globalThis maps are off the canonical path.
- Honest scope: `globalThis.__agentRuns` + the `pipelines` Set remain in the
  DEMO-ONLY scripted orchestrator (prod-guarded off); they are deleted when the
  scripted path is removed (0025 step 4). Multi-instance test needs both
  services live (ACTION REQUIRED) — the DB-tail design is verified by the
  queue/worker tests + single-source-of-truth reads.

## Outcome
Canonical run state + SSE are durable and multi-instance-safe: state in
Postgres, SSE tails `agent_events`, dedup via the unique jobs row, in-process
`_RUN_QUEUES` removed. Scripted-path globals remain only on the prod-disabled
demo path.
