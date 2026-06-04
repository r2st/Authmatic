# ADR 0007 — Tenant isolation (clinic_id + RLS)

- **Status:** accepted (partial — see "Status of enforcement")
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0006-multi-tenant-data-model-and-rls.md
- **Related:** [0005 auth](../../tickets/done/0005-replace-demo-auth-and-protect-api-routes.md), [ADR 0005 data model](0005-data-model-boundary.md), [ADR 0008 PHI](0008-phi-handling-policy.md)

## Context

Every PHI table was tenant-blind: no `clinic_id`, no RLS, and all web
queries used `getInsForgeAdmin()` (bypasses RLS). Isolation lived only in
application code, which is one missing `WHERE` away from a cross-tenant
leak.

## Decision

Defense in depth, two layers:

1. **Database (authoritative target).** `0007_multitenant_rls.sql` adds
   `clinic_id UUID NOT NULL REFERENCES clinics(id)` to `patients`,
   `prior_auths`, `agent_events`, `pa_submissions`, `compliance_scans`,
   `pa_embeddings`, and `users`; enables RLS; and adds a
   `tenant_isolation` policy per table:
   `USING (clinic_id = auth.clinic_id()) WITH CHECK (clinic_id = auth.clinic_id())`.
   The tenancy key reaches Postgres via the `app.clinic_id` session GUC,
   read by `auth.clinic_id()`.

2. **Application (interim enforced control).** App-layer ownership checks
   from ticket 0005 (`denyIfNotOwner`, clinic-scoped `listRuns`/
   `listSubmissions`) enforce tenancy today and remain as belt-and-braces.

### Client split

- `getInsForgeAdmin()` — BYPASSES RLS. Back-office only: seeds, audit
  writes, the `users`/auth lookup, admin reports. Commented as such.
- `getInsForgeClient(session)` (new, `lib/insforge/client.ts`) — the entry
  point for user-driven queries; carries `session.clinic_id`.

### Backfill

A stable default clinic (`…0001`) is inserted; existing rows are assigned
to it, then `clinic_id` is set `NOT NULL`.

## Status of enforcement (honest)

The DB policies are written but **not yet the enforced path**, because the
tenancy key must reach Postgres and our 0005 sessions are custom HMAC
cookies, not InsForge Auth JWTs. Two ways to close this (follow-up ticket):

1. **InsForge Auth JWT** whose claim maps to `auth.clinic_id()` — aligns
   with InsForge's native `auth.uid()`; requires migrating sessions to
   InsForge Auth.
2. **GUC-scoped pooled connection** — acquire a connection, `SET
   app.clinic_id = '<uuid>'` per request, run the query, reset. Works with
   our custom sessions; needs a dedicated pool (the InsForge SDK's pooled
   HTTP client doesn't expose per-request `SET`).

Neither is exercisable without the live InsForge backend, so
`getInsForgeClient()` currently delegates to admin while recording the
intended scope, and **app-layer checks (0005) are the enforced control**.
The manual `clinic_id` filtering in `submissions.ts` is deliberately
**kept** (not removed as the ticket suggested) until RLS is the live,
verified path — removing it now would drop enforcement to zero.

## Consequences

- Cross-tenant reads are blocked today by app-layer checks; the DB
  migration makes RLS a one-wiring-change away.
- The agent service (`apps/agent`) writes via its own pool — it must also
  present clinic context (`SET app.clinic_id`) once RLS is enforced;
  tracked in the follow-up.
- Negative test (clinic A reads clinic B → 404) is covered by app-layer
  checks now; the DB-level negative test lands with the scoped client +
  [[0010]].
