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
  // RLS enforcement is VERIFIED at the DB layer (ticket 0034): with
  // `0010_force_rls.sql` (FORCE RLS) + `0011_add_app_role.sql` (non-superuser
  // `authmatic_app`), a connection that `SET app.clinic_id = <clinic>` sees
  // only its own clinic's rows — proven against a real Postgres (cross-tenant
  // read returns 0). The remaining work is the DATA LAYER: the InsForge SDK is
  // HTTP and cannot set the GUC, so wiring this requires either (a) an InsForge
  // Auth JWT whose claim maps to auth.clinic_id(), or (b) a direct pg pool
  // connecting as `authmatic_app` and setting the GUC per request. Neither is
  // exercisable without the live InsForge backend / a new pg data layer, so
  // this still returns the admin client and app-layer ownership checks (0005)
  // remain the enforced control. See ADR 0007.
  return {
    db: getInsForgeAdmin().database,
    clinicId: session.clinic_id,
  };
}
