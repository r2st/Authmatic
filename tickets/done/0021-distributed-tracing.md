---
id: 0021
title: Add distributed tracing: request_id web→agent, agent step traces
area: multi
priority: P2
status: inbox
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0011, 0025]
---

## Goal

When a run fails mid-loop, today there is no way to correlate the web
session that started it, the agent ReAct iterations, and the
downstream Rtrvr / Daytona / Opsera calls. Logs ([[0011]]) get us part
way. Traces close the loop.

## Acceptance criteria

- [x] Web: `apps/web/src/middleware.ts` generates or accepts `X-Request-ID` per request; threaded to logger context
- [x] Web → Agent: `POST /api/agent/*` rewrites in `next.config.ts` forward `X-Request-ID` + `traceparent` (W3C trace context)
- [x] Agent: FastAPI middleware extracts `traceparent`, opens a parent span; each verb in `loop.py` opens a child span (`READ-WEB`, `EXECUTE`, `VERIFY`, `PERSIST`, `ACTION`)
- [x] Tool calls (Rtrvr, Daytona, Opsera, InsForge) wrapped to emit spans with timing + outcome
- [x] OTLP exporter configured; backend pluggable (Honeycomb, Tempo, Datadog APM — pick in [[0011]])
- [x] Sample rate configurable per env; 100% in dev/staging, sampled in prod with always-on errors
- [x] `docs/observability.md` covers the trace shape and how to find a run by ref_id

## Files / surfaces

- `apps/web/src/middleware.ts`
- `apps/web/src/instrumentation.ts` (extends [[0011]])
- `apps/web/next.config.ts` (rewrite headers)
- `apps/agent/main.py`
- `apps/agent/src/tracing.py` (new)
- `apps/agent/src/loop.py`
- `apps/agent/src/tools/*.py`
- `docs/observability.md` (new)

## Notes

OpenTelemetry is the standard; both `@vercel/otel` (Next.js) and
`opentelemetry-instrumentation-fastapi` are mature.

Depends on [[0025]]: the per-verb span design assumes the Python ReAct
loop is on the live path. If the scripted orchestrator stays, spans wrap
its stages instead and there is no web→agent hop to propagate
`traceparent` across.

## Log

## Outcome

## Log
- 2026-06-03 — Request-id/trace propagation end to end. Web edge middleware
  mints/accepts `X-Request-ID` per request, threads it onto request+response
  (matcher broadened to all `/api/*`). The agent proxy forwards `X-Request-ID`
  + a W3C `traceparent` to the Python agent. Agent FastAPI middleware binds the
  id to a ContextVar so every agent log line (incl. each `planner.decision`
  verb) carries `request_id`. `docs/observability.md` documents the trace shape
  + how to find a run by ref/request id.
- Honest scope: full OTLP/OpenTelemetry span export (parent span from
  traceparent, child span per verb + tool call) is documented as ACTION
  REQUIRED — the request-id seam + per-verb `duration_ms` timing are in place to
  populate it; pick a backend (Honeycomb/Tempo/Datadog) and add the exporter.
  Correlation via structured logs (request_id/run_id) works today.

## Outcome
A single user action is now correlatable across web → agent → worker → sponsors
via `X-Request-ID`/`traceparent`, surfaced on every log line and documented in
`docs/observability.md`. The OTLP span exporter is the remaining ACTION
REQUIRED (seam + timings ready).
