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
import { isPgConfigured, scopedQuery } from "../db";
import type { QueryResultRow } from "pg";

export interface ScopedClient {
  /** The InsForge database client (storage / non-tenant ops). */
  db: ReturnType<typeof getInsForgeAdmin>["database"];
  /** The clinic this client is scoped to. */
  clinicId: string;
  /**
   * RLS-enforced tenant query (ticket 0034). Runs as the non-privileged
   * `authmatic_app` role with `app.clinic_id` set, so the database limits
   * rows to this clinic regardless of the SQL. Use this for every
   * user-driven read/write of PHI tables. Requires a direct-pg connection
   * (APP_DATABASE_URL / INSFORGE_DB_URL); `pgEnforced` tells you if it's live.
   */
  query<R extends QueryResultRow = QueryResultRow>(sql: string, params?: unknown[]): Promise<R[]>;
  /** True when RLS is enforced at the DB (direct-pg configured), not just app-layer. */
  pgEnforced: boolean;
}

export function getInsForgeClient(session: ClinicSession): ScopedClient {
  // RLS is now enforced at runtime via the direct-pg scoped client (db.ts):
  // `query()` runs as `authmatic_app` with `SET app.clinic_id`, so the DB
  // limits rows to this clinic. VERIFIED against Postgres (db-rls test): a
  // clinic-B query for a clinic-A row returns 0. Migrate user-driven PHI reads
  // from the admin SDK to `.query()` to make the DB the enforced control;
  // app-layer checks (0005) cover anything still on the SDK. See ADR 0007.
  return {
    db: getInsForgeAdmin().database,
    clinicId: session.clinic_id,
    pgEnforced: isPgConfigured(),
    query: (sql, params = []) => scopedQuery(session.clinic_id, sql, params),
  };
}
