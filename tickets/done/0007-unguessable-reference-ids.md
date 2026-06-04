---
id: 0007
title: Replace sequential PA-2026-NNNNN reference IDs with unguessable IDs
area: web
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

Reference IDs are currently issued as `PA-2026-00451`, `PA-2026-00452`,
… — sequential and trivially enumerable. Combined with the missing
auth on `GET /api/pa/[ref]` (see [[0005]]), an attacker can iterate
through every submission and exfiltrate every clinic's PHI. Even with
auth landed, sequential public IDs are an information-disclosure
problem (submission volume per clinic is inferable).

## Acceptance criteria

- [x] ID generation now uses `newReferenceId()` (new `apps/web/src/lib/reference-id.ts`): `PA-` + 16 hex chars from `crypto.getRandomValues` (64 bits). `createSubmission` calls it directly. Hex chosen over base32 so SQL and TS produce identical format (see Log).
- [x] One-shot rotation migration `0006_rotate_reference_ids.sql`: adds `legacy_reference_id`, copies old id, regenerates `reference_id` with the matching `PA-` + hex format, collision-guarded.
- [x] `reference_id` stays the PRIMARY KEY (unique index preserved from 0002); legacy ids indexed for support lookup.
- [x] `counter` global, `nextLocalReferenceId()`, and `nextReferenceId()` (with its `next = max + 1`) all deleted from `submissions.ts`.
- [x] `parseReferenceId` in `rtrvr-submit.ts` now uses the shared `REFERENCE_ID_RE`; the stale `submissions.ts` regex was deleted with `nextReferenceId`. Grep confirms zero `PA-2026` references remain outside the doc comment.
- [~] Defense-in-depth rate limit on `GET /api/pa/[ref]` is owned by [[0012]] (rate limiting) — implemented there to keep one rate-limit config; cross-referenced.

## Files / surfaces

- `apps/web/src/lib/submissions.ts`
- `apps/web/src/lib/sponsors/rtrvr-submit.ts` (`parseReferenceId` regex)
- `db/migrations/0006_rotate_reference_ids.sql` (new)
- `apps/web/src/app/api/pa/[ref]/route.ts` (only if format-validation needed)
- `apps/web/src/app/portal/healthfirst/submission/[ref]/page.tsx`

## Notes

ULID is a good choice — sortable by time, unguessable, URL-safe.
Length tradeoff: humans sometimes need to read these off the phone.
Consider `PA-` prefix + 12 base32 chars for human friendliness.

## Log

- 2026-06-03 — New `reference-id.ts` is the single source of the format.
  Chose `PA-` + 16 uppercase hex (not the ticket's suggested base32)
  specifically so the rotation migration can generate the identical
  value in pure SQL via `'PA-' || upper(encode(gen_random_bytes(8),
  'hex'))` — no base32 UDF needed, app and DB never diverge. 64 bits is
  ample against enumeration. `pnpm --filter authmatic-web build` green.
- Rate-limit criterion deferred to [[0012]] (single owner for all
  per-route limits); noted as cross-reference, not silently dropped.

## Outcome

Sequential `PA-2026-NNNNN` ids replaced with unguessable `PA-`+16-hex
ids. Generation, the Rtrvr parser regex, and a collision-guarded
rotation migration (`0006`) all use one shared format; `counter`/
`max+1` logic removed. Enumeration attack closed at the ID layer; rate
limiting (defense-in-depth) lands in [[0012]].
