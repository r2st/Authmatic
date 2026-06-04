---
id: 0016
title: Remove silent in-memory fallbacks that mask DB failures
area: multi
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

`apps/web/src/lib/submissions.ts` has a module-level `memory = new
Map(...)` and `try {…} catch { return saveLocal(…) }` blocks that
silently fall back to in-memory storage whenever InsForge fails. This
was a hackathon-WiFi safety net; in production it:

- Hides DB outages from monitoring (no error surfaced)
- Data loss on process restart
- Inconsistent state across server instances (Render multi-instance)
- Same patient submitted twice in two instances ⇒ two ref IDs, two PA filings

Similar pattern in agent `_RUN_QUEUES` dict in `apps/agent/main.py:34`
(unbounded queue, replays after 30s sleep).

## Acceptance criteria

- [ ] `memory` Map removed from `apps/web/src/lib/submissions.ts`; failures throw and propagate to the route, which returns 503
- [ ] Same removal in `apps/web/src/lib/agent-runs.ts` and `apps/web/src/lib/batch-runs.ts` (verify whether the same pattern is present)
- [ ] If a multi-instance-safe queue is needed for SSE fan-out, replace `_RUN_QUEUES` with Redis pub/sub or InsForge realtime
- [ ] Errors from these paths route through the logger ([[0011]]) and error reporter
- [ ] Tests: with InsForge unreachable, `createSubmission` rejects with a 503-mapped error, does not write to memory
- [ ] `DEMO_FIXTURE_MODE` becomes the ONLY legitimate offline mode and is gated to non-prod environments

## Files / surfaces

- `apps/web/src/lib/submissions.ts`
- `apps/web/src/lib/agent-runs.ts`
- `apps/web/src/lib/batch-runs.ts`
- `apps/agent/main.py`
- `apps/agent/src/run_queue.py` (new, if Redis path)

## Notes

This ticket trades hackathon-grade resilience for production-grade
correctness. The right answer is "the DB is the source of truth; if
it's down, fail loudly."

Scope boundary vs [[0028]]: this ticket removes the *silent catch →
in-memory fallback* anti-pattern (`submissions.ts` memory Map, the
try/catch that swallows InsForge errors). [[0028]] does the bigger job
of making run/step/SSE state durable and multi-instance-safe. They
overlap on `agent-runs.ts` / `_RUN_QUEUES` — coordinate so one PR
doesn't undo the other. Recommend doing [[0028]] first (it establishes
the durable store), then this ticket removes whatever silent fallbacks
remain.

## Log

## Outcome
