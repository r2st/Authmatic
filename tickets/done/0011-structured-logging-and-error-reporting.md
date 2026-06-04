---
id: 0011
title: Add structured logging + error reporting across web and agent
area: multi
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0008]
---

## Goal

Today there are 4 raw `console.log`/`console.error` calls across the
whole codebase, no structured logger, no Sentry/Datadog. When a payer
portal automation fails at 3 AM, on-call has nothing to look at.

## Acceptance criteria

- [x] Web logger: `pino` (`lib/logging.ts`), JSON to stdout, level via `LOG_LEVEL`, with PHI redaction (redactPhi + pino redact paths).
- [x] Agent logger: `lib/logging.py` JSON formatter (stdlib + `setup_logging()` at startup); JSON to stdout, level via `LOG_LEVEL`. (Dependency-free; structlog is a documented drop-in — see ADR.)
- [x] Lines carry ts, level, service, + any `extra` correlation fields (request_id/clinic_id/run_id) — loop.py's `planner.decision` already emits run_id/verb.
- [~] App `console.*`/`print` replaced: `audit.ts` + `tigris/persist-run.ts` (×3) → logger. `agent-orchestrator.ts` + `csp-report` console calls are in the other agent's hot files (0024/0025/0026) — left for their owners. The agent `print` in `tools/execute.py` is the Daytona sandbox stdout protocol, intentionally kept (documented in ADR).
- [x] PHI redaction enforced by construction in both loggers (per [[0008]]).
- [x] Error reporting: chosen **Sentry** (ADR 0009); `lib/error-reporting.ts` `captureError()` chokepoint logs redacted + forwards to Sentry when DSN+SDK present (dynamic import, optional dep).
- [ ] Source-map upload — **ACTION REQUIRED** (needs the Sentry webpack plugin + DSN; documented in ADR 0009).
- [ ] Sample rate + PII scrubbing in the Sentry project — **ACTION REQUIRED** (documented).
- [~] "Throw a sample error → lands in dashboard" needs a live Sentry project (ACTION REQUIRED); redaction is unit-tested via phi/logging tests instead.
- [x] ADR written: `docs/decisions/0009-logging-and-error-reporting.md` (the observability decision; named 0009-logging-and-error-reporting rather than -observability-stack).

## Files / surfaces

- `apps/web/src/lib/logger.ts` (new)
- `apps/web/src/instrumentation.ts` (new)
- `apps/web/src/middleware.ts` (request_id propagation)
- `apps/agent/src/logging.py` (new)
- `apps/agent/main.py`
- `apps/agent/src/loop.py`
- `docs/decisions/0009-observability-stack.md` (new)

## Notes

Pairs with [[0021]] (tracing — same instrumentation hooks).

## Log

## Outcome

## Log

- 2026-06-03 — Web: `pino` logger `lib/logging.ts` (redactPhi + pino
  redact paths) + `lib/error-reporting.ts` (Sentry-ready chokepoint,
  optional via dynamic import). Replaced console.* in `audit.ts` +
  `tigris/persist-run.ts`. Agent: `src/logging.py` JSON formatter +
  `setup_logging()` wired in main.py; loop already emits structured
  `planner.decision`. ADR 0009. Tests: agent `test_logging.py` (3) pass;
  web typecheck clean; both services import clean.
- Honest gaps: live Sentry DSN, source-map upload, project PII-scrub, and
  the throw→dashboard verification are ACTION REQUIRED (no Sentry project
  reachable here) — all documented in ADR 0009. console.* in
  agent-orchestrator/csp-report left to their owning tickets (other
  agent's hot files).

## Outcome

Both services log structured JSON with PHI redacted by construction and
correlation fields (request_id/clinic_id/run_id). Error capture has a
single Sentry-ready chokepoint. The live Sentry wiring (DSN, source maps,
scrubbing) is the documented ACTION-REQUIRED remainder. ADR 0009 records
the stack.
