# Observability

How to trace a prior-auth run across web → agent → worker → sponsors.
Pairs with [ADR 0009 logging](decisions/0009-logging-and-error-reporting.md).

## Correlation id (ticket 0021)

- The web edge middleware (`apps/web/src/middleware.ts`) mints an
  `X-Request-ID` on every API request (or accepts an inbound one) and threads
  it onto the request + response.
- The agent proxy (`apps/web/src/lib/agent-proxy.ts`) forwards `X-Request-ID`
  **and** a W3C `traceparent` to the Python agent on `/api/run` + `/api/stream`.
- The agent's FastAPI middleware (`apps/agent/main.py`) binds the inbound
  `X-Request-ID` to a `ContextVar`, so every agent log line in that request —
  including each `planner.decision` (one per ReAct verb) — carries `request_id`.

## Trace shape

```
X-Request-ID  ─┬─ web: POST /api/run            (rate-limit, auth, enqueue)
               ├─ agent: POST /api/run          (validate, enqueue job)
               ├─ worker: job.start / planner.decision ×N / job.done
               │     └─ per verb: EXECUTE / READ-WEB / VERIFY / PERSIST / ACTION
               │           └─ tool calls: Daytona / Rtrvr / Opsera / InsForge
               └─ web: GET /api/stream/[id]      (tail durable agent_events)
```

Each `agent_events` row carries `duration_ms` per verb; `job.*` and
`planner.decision` log lines carry `run_id` + `request_id`.

## Finding a run

- **By reference id / run id:** grep logs for `run_id=<id>`; the audit page
  `/run/[id]` renders the durable `agent_events` timeline.
- **By request id:** grep `request_id=<X-Request-ID>` across web + agent logs to
  reconstruct the full path of a single user action.
- **Stuck / failed runs:** `jobs` table — `status IN ('failed','dead')` with
  `last_error`; the worker logs `job.failed`.

## Metrics worth watching

- Per-verb `duration_ms` (sponsor latency; ticket 0026 made wall-clock real).
- Job queue depth (`SELECT count(*) FROM jobs WHERE status='queued'`) + dead
  count.
- `needs_review` runs (ticket 0029 — extraction couldn't identify the patient).

## OTLP exporter (ACTION REQUIRED)

The request-id/traceparent seam is in place; wiring a real distributed-tracing
backend is the remaining step:

- Pick a backend (Honeycomb / Grafana Tempo / Datadog APM).
- Add the OpenTelemetry SDK + OTLP exporter to web (`instrumentation.ts`) and
  agent; open a parent span from `traceparent` and a child span per verb +
  tool call (the `agent_events` timing already exists to populate them).
- Sample 100% in dev/staging, sample in prod with always-on error traces.

Until then, correlation is via the structured logs above (request_id/run_id),
which is sufficient to follow any single run end-to-end.
