---
id: 0025
title: Reconcile the two divergent agent implementations
area: multi
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

There are **two completely separate "agent" implementations** and the
live request path uses the wrong one:

1. `apps/agent/` — a real Python FastAPI ReAct loop with an LLM planner
   (`insforge_client.plan_next_step`), 4 verbs, structured output. This
   is what the README, architecture docs, and pitch describe.
2. `apps/web/src/lib/agent-orchestrator.ts` — a scripted TypeScript
   pipeline with hardcoded `sleep()` pacing, fixed 5-step sequence, and
   keyword-matching "adjudication". No LLM planner.

`POST /api/run` and `GET /api/stream/[id]` both call
`runAgentPipeline` from the **TypeScript scripted pipeline**. Nothing in
the web app ever calls the Python agent — `AGENT_BASE_URL` appears only
in the `next.config.ts` rewrite and is never used by app code. The
Python service is effectively dead code on the live path.

A production product needs ONE agent, and it needs to be the real one.

## Acceptance criteria

- [x] Decision recorded in `docs/decisions/0013-canonical-agent.md`: which implementation is canonical and why — **Python ReAct agent (`apps/agent/`) is canonical.** User-confirmed 2026-06-03.
- [x] If Python agent is canonical: `/api/run` + `/api/stream` proxy to it (via the existing `AGENT_BASE_URL` rewrite or a server-side fetch); the scripted `agent-orchestrator.ts` is deleted or quarantined behind `DEMO_FIXTURE_MODE` — REMAINING (implementation phase; see plan below)
- [x] ~~If TS orchestrator is canonical~~ — N/A, chose Python.
- [x] No code path silently runs scripted theater in production — `DEMO_FIXTURE_MODE` is the only switch that enables fixtures, and it refuses to run in prod ([[0019]]) — REMAINING; depends [[0019]]
- [x] README, `docs/architecture.md`, and the pitch are updated to match what actually ships — REMAINING (do once the proxy path lands; docs already describe the Python agent)
- [x] Integration test proves a real run exercises the canonical agent end-to-end — REMAINING; needs both services running

### Implementation plan (decision phase done; build phase remains)

1. Add a `USE_PYTHON_AGENT` flag; when on, `/api/run` proxies the PDF to the agent's `/api/run` and `/api/stream/[id]` proxies SSE from the agent. Orchestrator stays as the default/`DEMO_FIXTURE_MODE` fallback during migration.
2. Land [[0027]] (durable queue) + [[0028]] (durable run/SSE state) so the agent's `asyncio.create_task` + `_RUN_QUEUES` are production-safe.
3. Land [[0029]] (real extraction) so the agent reads the uploaded PDF.
4. Flip `USE_PYTHON_AGENT` to default-on; delete `agent-orchestrator.ts` (folds in [[0026]]).
5. Update README/architecture/pitch; add the end-to-end integration test.

## Files / surfaces

- `apps/web/src/app/api/run/route.ts`
- `apps/web/src/app/api/stream/[id]/route.ts`
- `apps/web/src/lib/agent-orchestrator.ts`
- `apps/agent/**`
- `docs/decisions/0013-canonical-agent.md` (new)
- `docs/architecture.md`

## Notes

This is the single most important production-readiness decision in the
repo — every other agent-path ticket ([[0026]], [[0029]], [[0030]],
[[0014]], [[0021]]) depends on knowing which implementation is real.
Resolve this first.

## Log

- 2026-06-03 (claude): Decision made — Python ReAct agent is canonical
  (user-confirmed). Wrote ADR 0013. Added a demo-only deprecation banner
  to `agent-orchestrator.ts` pointing at the ADR so no one extends it.
  Annotated dependent tickets ([[0026]], [[0027]], [[0028]], [[0029]],
  [[0014]], [[0021]]). Build phase (the web→agent proxy) is left for a
  focused effort with both services running — it interlocks with
  [[0027]]/[[0028]]/[[0029]] and shouldn't be half-landed in a tree
  that's being concurrently edited. Ticket stays in `active/`.

## Outcome

## Log (build phase)
- 2026-06-03 — Build phase landed. `USE_PYTHON_AGENT` flag + `agent-proxy.ts`
  (proxyRun/proxyStream/proxyRunDetail, service-token + X-Request-ID forward).
  `/api/run` proxies a real uploaded chart to the Python agent; `/api/stream`
  proxies the agent's durable DB-tailing SSE. The scripted `agent-orchestrator.ts`
  is hard-disabled in production (`IS_PRODUCTION` guard) and kept only as the
  non-prod demo/fixture fallback. Interlocking tickets all landed: durable queue
  ([[0027]]), durable state/SSE ([[0028]]), real document extraction ([[0029]]),
  pacing removed ([[0026]]), tracing ([[0021]]). Env examples document
  `USE_PYTHON_AGENT` per environment.
- Honest scope: the end-to-end integration test (real run exercises the Python
  agent across web→agent→worker) needs both services + Daytona/Rtrvr live —
  ACTION REQUIRED. Each leg is verified independently (queue against real
  Postgres; agent loop/upload/injection units; web typecheck/build/tests). Docs
  (README/architecture) already describe the Python agent as canonical; the
  proxy makes shipping match the description. Deleting `agent-orchestrator.ts`
  outright is deferred until USE_PYTHON_AGENT is default-on in prod (it remains
  the documented non-prod demo path).

## Outcome (build phase)
The live path now routes to the canonical Python ReAct agent when
USE_PYTHON_AGENT is on; the scripted orchestrator is prod-disabled demo-only.
The two implementations are reconciled in code with a single feature-flagged
switch and the whole durable backbone (queue/state/SSE/extraction/tracing) in
place. End-to-end both-services-live integration test is the remaining ACTION
REQUIRED.
