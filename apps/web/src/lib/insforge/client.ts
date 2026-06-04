/**
 * Tenant-scoped InsForge client (ticket 0006).
 *
 * `getInsForgeAdmin()` (admin.ts) bypasses RLS and must be used only for
 * back-office tooling (seeds, audit writes, the auth/users lookup). All
 * USER-DRIVEN queries should go through `getInsForgeClient(session)`, which
 * carries the caller's clinic so the database's RLS policies
 * (db/migrations/0007_multitenant_rls.sql) scope every row.
 *
 * Status: the scoping mechanism depends on how the tenancy key reaches
 * Postgres. Two supported paths (see ADR 0007):
 *   1. InsForge Auth JWT whose claim maps to `auth.clinic_id()`.
 *   2. A GUC-scoped pooled connection that runs `SET app.clinic_id = <uuid>`.
 *
 * Neither can be exercised without the live InsForge backend, so this module
 * currently returns the admin client AND records the intended clinic scope,
 * while app-layer ownership checks (ticket 0005) enforce tenancy in the
 * interim. Swapping the body for a real scoped client is the only change
 * needed once the JWT/GUC path is wired — call sites already pass `session`.
 *
 * Server-only.
 */
import { getInsForgeAdmin } from "./admin";
import type { ClinicSession } from "../auth/session";

export interface ScopedClient {
  /** The InsForge database client. */
  db: ReturnType<typeof getInsForgeAdmin>["database"];
  /** The clinic this client is scoped to (for SET app.clinic_id / JWT claim). */
  clinicId: string;
}

export function getInsForgeClient(session: ClinicSession): ScopedClient {
  // TODO(0006 follow-up): issue an InsForge JWT for session.clinic_id, or
  // acquire a pooled connection and `SET app.clinic_id`. Until then, RLS is
  // defense-in-depth and app-layer checks (0005) are the enforced control.
  return {
    db: getInsForgeAdmin().database,
    clinicId: session.clinic_id,
  };
}
