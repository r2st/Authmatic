---
id: 0011
title: Add structured logging + error reporting across web and agent
area: multi
priority: P1
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: [0008]
---

## Goal

Today there are 4 raw `console.log`/`console.error` calls across the
whole codebase, no structured logger, no Sentry/Datadog. When a payer
portal automation fails at 3 AM, on-call has nothing to look at.

## Acceptance criteria

- [ ] Web logger added (`pino` or `next-logger`); JSON output, levels via env
- [ ] Agent logger added (`structlog`); JSON output to stdout
- [ ] Every log line includes: timestamp, level, service, request_id, clinic_id (if available), run_id (if applicable)
- [ ] All raw `console.*` and `print()` calls replaced
- [ ] PHI redaction wrapper enforced (per [[0008]]): `logger.info("submission.created", {ref: redact(ref), clinic_id})` — never raw patient fields
- [ ] Error reporting wired: Sentry (or Datadog, decide and ADR) on web (`apps/web/src/instrumentation.ts`) and agent (`sentry-sdk`)
- [ ] Source-map upload to error reporter at build time
- [ ] Sample rate + PII scrubbing rules configured in Sentry/DD project
- [ ] Test: throw a sample error in dev, confirm it lands in the dashboard with PHI redacted
- [ ] `docs/decisions/0009-observability-stack.md` written

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
