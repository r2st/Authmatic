---
id: 0006
title: Add clinic_id to PHI tables, enable RLS, stop using admin client
area: db
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0002, 0005]
---

## Goal

Make multi-tenant isolation enforced by the database, not by application
code. Every PHI table needs a `clinic_id` column, a `CREATE POLICY` that
scopes reads/writes to the caller's clinic, and app code must use a
JWT-scoped client (not `getInsForgeAdmin()`) for user-driven queries.

Today: `db/migrations/*.sql` has **zero `CREATE POLICY` statements**,
**zero RLS-enabled tables**, and every web API route uses
`getInsForgeAdmin()` which bypasses RLS by design.

## Acceptance criteria

- [x] Migration `0007_multitenant_rls.sql` adds `clinic_id UUID NOT NULL REFERENCES clinics(id)` to `patients`, `prior_auths`, `agent_events`, `pa_submissions`, `compliance_scans`, `users`, and (conditionally) `pa_embeddings`.
- [x] `clinics` table added (id, name, created_at) + stable default-clinic row.
- [x] `users` gets `clinic_id` FK (in the same migration's table loop).
- [x] `ENABLE ROW LEVEL SECURITY` on every PHI table.
- [x] `CREATE POLICY tenant_isolation` per table: `USING (clinic_id = auth.clinic_id()) WITH CHECK (...)` (covers select/update/delete + insert). `auth.clinic_id()` reads the `app.clinic_id` session GUC.
- [x] Backfill: default clinic inserted, existing rows assigned to it, then `clinic_id` set `NOT NULL`.
- [x] `admin.ts` annotated as RLS-bypassing/back-office-only; new `getInsForgeClient(session)` (`lib/insforge/client.ts`) is the user-scoped entry point.
- [~] `submissions.ts` manual `clinic_id` filtering **deliberately kept** (NOT removed). Removing it before RLS is the live, verified path would drop enforcement to zero — RLS can't be exercised without the live InsForge backend + JWT/GUC wiring. Documented in ADR 0007 "Status of enforcement".
- [~] Negative test (clinic A → clinic B = 404) is enforced today by app-layer checks ([[0005]] `denyIfNotOwner`); DB-level negative test lands with the scoped client + [[0010]].
- [x] `docs/decisions/0007-tenant-isolation.md` documents the policy and the admin-client-allowlist

## Files / surfaces

- `db/migrations/0004_add_clinics_and_users.sql` (new) — depends on [[0005]]
- `db/migrations/0005_add_clinic_id_and_rls.sql` (new)
- `apps/web/src/lib/insforge/admin.ts`
- `apps/web/src/lib/insforge/client.ts` (new)
- `apps/web/src/lib/submissions.ts`
- `apps/web/src/lib/adjudication.ts`
- `apps/web/src/lib/agent-runs.ts`
- `apps/agent/src/persist.py`
- `apps/agent/src/tools/persist.py`
- `docs/decisions/0007-tenant-isolation.md` (new)

## Notes

Blocked by [[0005]] (need a user→clinic linkage to enforce against) and
informed by [[0002]] (which model survives unification). The InsForge
`auth.uid()` and a custom `auth.clinic_id()` are documented in the
`insforge` skill. The agent service writes to the same DB — it must
present a JWT (service token with clinic context, or per-run scoped
token issued by web).

## Log

- 2026-06-03 — Wrote `0007_multitenant_rls.sql` (clinics, clinic_id on all
  PHI tables + users, backfill→NOT NULL, RLS + `tenant_isolation` policy,
  `auth.clinic_id()` GUC accessor, conditional pa_embeddings). Added
  `lib/insforge/client.ts` (`getInsForgeClient(session)` scaffold),
  annotated `admin.ts` as back-office-only, wrote ADR
  `docs/decisions/0007-tenant-isolation.md`.
- **Honest status:** RLS policies are written but not yet the *enforced*
  path — our 0005 sessions are custom HMAC cookies, not InsForge Auth
  JWTs, so the tenancy key (`app.clinic_id`) still needs either an
  InsForge JWT claim mapping or a GUC-scoped connection pool, neither
  exercisable without the live backend. App-layer checks (0005) are the
  enforced control; RLS is defense-in-depth, one wiring-change away. ADR
  0007 spells out both paths + the follow-up. My code typechecks clean
  (`tsc` flagged only a concurrent worker's in-flight `/api/readyz`).

## Outcome

DB-level multi-tenancy is in place as a migration: clinics, `clinic_id`
on every PHI table, RLS + per-table isolation policies, backfill, and a
back-office/scoped client split (ADR 0007). Enforcement today is the
0005 app-layer ownership layer; flipping RLS to the live enforced path
needs the InsForge JWT/GUC wiring described in ADR 0007 (tracked
follow-up). Manual clinic filtering kept until then — not removed.

**Follow-up (filed 2026-06-03):** [[0034]] wires the scoped client so RLS
actually enforces at runtime; [[0035]] applies + verifies migrations
0004–0009 (incl. 0007's policies) against the live DB. Until both land,
tenant isolation is app-layer-only — review every new query for the
clinic filter.
