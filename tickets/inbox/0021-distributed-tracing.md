---
id: 0021
title: Add distributed tracing: request_id web→agent, agent step traces
area: multi
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: [0011, 0025]
---

## Goal

When a run fails mid-loop, today there is no way to correlate the web
session that started it, the agent ReAct iterations, and the
downstream Rtrvr / Daytona / Opsera calls. Logs ([[0011]]) get us part
way. Traces close the loop.

## Acceptance criteria

- [ ] Web: `apps/web/src/middleware.ts` generates or accepts `X-Request-ID` per request; threaded to logger context
- [ ] Web → Agent: `POST /api/agent/*` rewrites in `next.config.ts` forward `X-Request-ID` + `traceparent` (W3C trace context)
- [ ] Agent: FastAPI middleware extracts `traceparent`, opens a parent span; each verb in `loop.py` opens a child span (`READ-WEB`, `EXECUTE`, `VERIFY`, `PERSIST`, `ACTION`)
- [ ] Tool calls (Rtrvr, Daytona, Opsera, InsForge) wrapped to emit spans with timing + outcome
- [ ] OTLP exporter configured; backend pluggable (Honeycomb, Tempo, Datadog APM — pick in [[0011]])
- [ ] Sample rate configurable per env; 100% in dev/staging, sampled in prod with always-on errors
- [ ] `docs/observability.md` covers the trace shape and how to find a run by ref_id

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
