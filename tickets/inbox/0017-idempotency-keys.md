---
id: 0017
title: Add idempotency keys to /api/run and /api/pa/submit
area: web
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

A user double-clicking "Submit" today fires two POSTs to `/api/pa/submit`
which create two separate `pa_submissions` rows with two reference IDs
for the same patient. Same for `/api/run` — duplicate clicks trigger
two agent loops, two Rtrvr submissions, two payer-portal filings. With
real payers, this is a duplicate-submission incident.

## Acceptance criteria

- [ ] Both endpoints accept an `Idempotency-Key` header (stripe-style)
- [ ] First request stores `(key, clinic_id) → response` for 24 h
- [ ] Subsequent request with same key + same clinic returns the cached response (200 with original body), does not re-execute
- [ ] Different key → new operation
- [ ] Same key + different request body → 422 with `idempotency_conflict`
- [ ] Storage: InsForge KV table or Redis (whatever [[0012]] picks)
- [ ] Client (web frontend) generates a UUID per form submission and retries with the same key
- [ ] Tests cover all four cases above

## Files / surfaces

- `apps/web/src/lib/idempotency.ts` (new)
- `apps/web/src/app/api/run/route.ts`
- `apps/web/src/app/api/pa/submit/route.ts`
- `apps/web/src/app/portal/healthfirst/prior-auth/page.tsx` (client key generation)
- `db/migrations/000X_add_idempotency_keys.sql` (new)

## Notes

Coordinate storage with [[0012]] — same backing store.

Idempotency is also the guard for two double-filing paths surfaced
elsewhere: at-least-once job redelivery in [[0027]] (durable queue) and
duplicate-pipeline starts from multi-instance SSE in [[0028]]. The
idempotency key must be checked at the point the PA is actually filed to
the payer (the SUBMIT/ACTION step), not just at HTTP ingress — a
redelivered job re-enters below the HTTP layer.

## Log

## Outcome
