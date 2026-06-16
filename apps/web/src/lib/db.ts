/**
 * Tenant-scoped Postgres access (ticket 0034 runtime enforcement).
 *
 * The InsForge HTTP SDK can't set a Postgres session GUC, so it can't drive
 * RLS. This module connects directly as the non-privileged `authmatic_app`
 * role (migration 0011) and runs every user-driven query inside a transaction
 * that `SET LOCAL app.clinic_id = <session.clinic_id>` — so the
 * tenant_isolation policies (migrations 0007 + 0010 FORCE RLS) are enforced by
 * the database. A second clinic physically cannot read the first clinic's
 * rows, even if app code forgets a `WHERE clinic_id = …`.
 *
 * `adminQuery` uses a privileged connection for legitimately cross-tenant
 * back-office work (seeds, audit writes, the public payer-portal surface).
 *
 * Connection strings:
 *   APP_DATABASE_URL    → connects as authmatic_app (RLS-enforced). Falls back
 *                         to INSFORGE_DB_URL if unset.
 *   ADMIN_DATABASE_URL  → privileged/owner connection. Falls back to
 *                         INSFORGE_DB_URL.
 *
 * Server-only.
 */
import { Pool, type PoolClient, type QueryResultRow } from "pg";

let _appPool: Pool | null = null;
let _adminPool: Pool | null = null;

function appPool(): Pool {
  if (!_appPool) {
    const cs = process.env.APP_DATABASE_URL || process.env.INSFORGE_DB_URL;
    if (!cs) throw new Error("APP_DATABASE_URL / INSFORGE_DB_URL not set");
    _appPool = new Pool({ connectionString: cs, max: 10 });
  }
  return _appPool;
}

function adminPool(): Pool {
  if (!_adminPool) {
    const cs = process.env.ADMIN_DATABASE_URL || process.env.INSFORGE_DB_URL;
    if (!cs) throw new Error("ADMIN_DATABASE_URL / INSFORGE_DB_URL not set");
    _adminPool = new Pool({ connectionString: cs, max: 5 });
  }
  return _adminPool;
}

/** True if a direct-pg connection string is configured (else callers fall back to the SDK). */
export function isPgConfigured(): boolean {
  return Boolean(
    process.env.APP_DATABASE_URL ||
      process.env.ADMIN_DATABASE_URL ||
      process.env.INSFORGE_DB_URL
  );
}

/**
 * Run `fn` inside a transaction scoped to `clinicId` (RLS-enforced). The GUC is
 * SET LOCAL so it's bound to this transaction only and never leaks across
 * pooled connections.
 */
export async function withClinic<T>(
  clinicId: string,
  fn: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await appPool().connect();
  try {
    await client.query("BEGIN");
    // set_config(..., true) = SET LOCAL: scoped to this transaction.
    await client.query("SELECT set_config('app.clinic_id', $1, true)", [clinicId]);
    const out = await fn(client);
    await client.query("COMMIT");
    return out;
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}

/** Tenant-scoped query: RLS limits rows to `clinicId`'s clinic. */
export async function scopedQuery<R extends QueryResultRow = QueryResultRow>(
  clinicId: string,
  sql: string,
  params: unknown[] = []
): Promise<R[]> {
  return withClinic(clinicId, async (client) => {
    const res = await client.query<R>(sql, params);
    return res.rows;
  });
}

/** Privileged query (bypasses RLS). Back-office / public-portal use ONLY. */
export async function adminQuery<R extends QueryResultRow = QueryResultRow>(
  sql: string,
  params: unknown[] = []
): Promise<R[]> {
  const res = await adminPool().query<R>(sql, params);
  return res.rows;
}

/** Close pools (tests / graceful shutdown). */
export async function closePools(): Promise<void> {
  await _appPool?.end();
  await _adminPool?.end();
  _appPool = null;
  _adminPool = null;
}
