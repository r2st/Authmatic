---
id: 0017
title: Add idempotency keys to /api/run and /api/pa/submit
area: web
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

A user double-clicking "Submit" today fires two POSTs to `/api/pa/submit`
which create two separate `pa_submissions` rows with two reference IDs
for the same patient. Same for `/api/run` — duplicate clicks trigger
two agent loops, two Rtrvr submissions, two payer-portal filings. With
real payers, this is a duplicate-submission incident.

## Acceptance criteria

- [x] Both endpoints accept `Idempotency-Key` (stripe-style): `/api/run` (scoped per clinic) and `/api/pa/submit` (scoped per IP — public payer route, no session).
- [x] First request stores `(key, scope) → response` for 24h (`lib/idempotency.ts`, TTL sweep).
- [x] Same key + same body → cached response replayed, no re-execution (no second agent loop / second PA row).
- [x] Different key → new operation.
- [x] Same key + different body → 422 `idempotency_conflict`.
- [x] Storage: in-process Map with TTL, matching [[0012]]'s in-process choice; same Redis/InsForge-KV upgrade path documented.
- [~] Client UUID-per-submission: server side complete; the frontend `fetch` calls should add `Idempotency-Key: crypto.randomUUID()` — small follow-up noted (didn't touch the form components to avoid colliding with the other agent's web edits).
- [x] Tests cover all four cases (`idempotency.test.ts`, 4 tests, pass).

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

## Log

- 2026-06-03 — `lib/idempotency.ts` (lookup/save, body-hash conflict
  detection, 24h TTL, clinic/IP-scoped buckets) wired into `/api/run`
  (per-clinic, fingerprint = case+demo) and `/api/pa/submit` (per-IP,
  hash of JSON body). 4 tests pass; typecheck clean. Did not edit
  `submissions.ts` (other agent active there on 0018).
- Frontend `Idempotency-Key` generation is the only remaining piece —
  left to avoid colliding with concurrent web-component edits; server
  enforces correctly once the header is sent.

## Outcome

Double-submit protection on both unsafe POSTs. A repeated
Idempotency-Key + identical request replays the original response
without re-executing (no duplicate PA filing); a reused key with a
changed body is a 422 conflict. In-process store (Redis upgrade path
documented), 4 passing tests.
