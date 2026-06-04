---
id: 0016
title: Remove silent in-memory fallbacks that mask DB failures
area: multi
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
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

- [x] Silent fallback removed from `submissions.ts`: every method now throws `PersistenceError` on DB failure / missing-DB-outside-fixture-mode instead of writing to the memory Map. Routes (`pa/[ref]`, `pa/submit`, `dashboard`) map it to **503** via `lib/persistence-response.ts` `to503()`.
- [~] `agent-runs.ts` / `batch-runs.ts`: the same global-Map pattern is present BUT it is the run-state store, not a DB-masking fallback — making it durable is explicitly ticket [[0028]] (durable run state, blocked on [[0025]]). Verified + scoped out here; noted.
- [~] `_RUN_QUEUES` Redis/realtime replacement = ticket [[0028]] (durable SSE, blocked on [[0025]]). Not in this ticket's reach.
- [x] Errors route through the structured logger ([[0011]]): `submission.{create,read,update,list}_failed` log lines before throwing.
- [x] Test (`submissions-failopen.test.ts`): InsForge unconfigured + non-fixture → `createSubmission`/`listSubmissions` reject with `PersistenceError` (route → 503), no memory write. 3 tests pass.
- [x] `DEMO_FIXTURE_MODE` (`isDemoFixtureMode()`) is now the ONLY path that permits the in-memory store (`memoryAllowed()`); prod-gating of the flag itself is ticket [[0019]] (other agent active) — cross-referenced.

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

## Log

- 2026-06-03 — Rewrote `submissions.ts` persistence: added
  `PersistenceError`, `memoryAllowed()` (= `isDemoFixtureMode()`), and
  removed every silent `catch → saveLocal`/`return memory`. DB errors
  now log (0011) + throw; missing DB outside fixture mode throws. Added
  `lib/persistence-response.ts` `to503()` and wired it into `pa/[ref]`,
  `pa/submit`, `dashboard`. Preserved the 0018 allowlist machinery
  untouched. 37 web tests pass (3 new fail-loud), typecheck clean.
- Scoped out (different tickets): the `agent-runs`/`batch-runs` global
  Maps and `_RUN_QUEUES` are run-state/SSE infra → durable replacement
  is [[0028]] (blocked on [[0025]]); `DEMO_FIXTURE_MODE` prod-gating is
  [[0019]] (other agent). The `adjudicate` route's 503-mapping left to
  its owner ([[0030]] hot file) — PersistenceError there degrades to 500.

## Outcome

The PA submission path no longer hides DB outages behind an in-memory
Map: failures throw `PersistenceError` → 503, logged via the structured
logger. Fixture mode is the sole legitimate offline path. Run-state /
SSE durability (agent-runs, _RUN_QUEUES) is correctly deferred to
[[0028]]; the silent-data-loss risk on submissions is closed. 3 new
passing tests.
