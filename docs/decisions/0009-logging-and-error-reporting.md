# ADR 0009 — Structured logging + error reporting

- **Status:** accepted (logging live; error-reporter scaffolded, DSN ACTION REQUIRED)
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0011-structured-logging-and-error-reporting.md
- **Related:** [ADR 0008 PHI](0008-phi-handling-policy.md), [[0021]] (tracing builds on the request_id field)

## Context

The codebase logged via a handful of `console.*` / `print` calls — no
structure, no levels, no correlation ids, no error aggregation. On-call had
nothing to triage a 3 AM failure with.

## Decision

**Logging.** Structured JSON to stdout on both services.
- Web: `pino` (`apps/web/src/lib/logging.ts`) — `log.info/warn/error(event,
  context)`; every context object passes through `redactPhi` (ADR 0008) AND
  pino's `redact` paths, so PHI cannot reach a log line. `log.child({
  request_id, clinic_id })` for per-request correlation.
- Agent: stdlib `logging` + a JSON formatter (`apps/agent/src/logging.py`,
  `setup_logging()` called at startup). Caller-supplied `extra=` fields
  (request_id, clinic_id, run_id) surface as structured fields. Callers
  redact PHI at the call site (loop.py already does).
- Why pino + stdlib over heavier stacks: pino is the standard fast JSON
  logger for Node; stdlib+formatter avoids a new agent dependency. `structlog`
  is a drop-in upgrade later — call sites don't change.

**Error reporting.** **Sentry** (chosen over Datadog APM: simpler PHI
scrubbing config, first-class Next.js + Python SDKs, cheaper at our scale).
- A single chokepoint `captureError(err, context)`
  (`apps/web/src/lib/error-reporting.ts`) logs the (redacted) error and, when
  `SENTRY_DSN` is set and `@sentry/nextjs` is installed, forwards it. The SDK
  is a dynamic import so the app builds with or without Sentry.

## PHI scrubbing

Both loggers redact known PHI keys (member_id, patient_name, dob, ssn,
justification, rationale) by construction. Sentry must additionally enable
server-side data scrubbing + `beforeSend` PII filtering.

## ACTION REQUIRED (human)

- Install `@sentry/nextjs` (web) + `sentry-sdk` (agent); set `SENTRY_DSN`
  per environment.
- Add `sentry.client/server.config.ts` (or `instrumentation.ts`) with sample
  rate (100% errors; trace sample per env) + `beforeSend` PII scrub.
- Wire source-map upload at build time (`@sentry/nextjs` webpack plugin) so
  stack traces de-minify.
- Verify: throw a test error in staging, confirm it lands with PHI redacted.

## Consequences

- All app `console.*` / `print` are replaced by the structured loggers (the
  one remaining `print` in `tools/execute.py` is the Daytona sandbox stdout
  protocol, not logging — intentionally left).
- The `request_id` field is the seam ticket [[0021]] extends into full
  distributed tracing.
