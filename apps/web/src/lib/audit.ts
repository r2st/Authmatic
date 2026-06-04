/**
 * Audit log writer — who read or mutated which PHI resource, when.
 *
 * Backs the audit_log table (db/migrations/0004_add_audit_log.sql) required
 * by ADR 0008 + HIPAA §164.312(b). Best-effort and non-blocking: an audit
 * write must never fail the user request, but a failure IS logged so the
 * gap is visible (a silently-missing audit trail is itself a finding).
 *
 * `detail` must contain only redacted/non-PHI context (use lib/phi.ts).
 * Actor identity is threaded from the session by ticket 0005; until a
 * session exists, `actor_id` is null (system/agent action).
 */
import { getInsForgeAdmin, isInsForgeConfigured } from "./insforge/admin";

export type AuditAction =
  | "read"
  | "create"
  | "update"
  | "delete"
  | "adjudicate"
  | "login"
  | "access_denied";

export interface AuditEntry {
  action: AuditAction;
  resource: string;
  resource_id?: string;
  actor_id?: string | null;
  actor_clinic?: string | null;
  allowed?: boolean;
  detail?: Record<string, unknown>;
}

export async function auditLog(entry: AuditEntry): Promise<void> {
  if (!isInsForgeConfigured()) return; // demo/no-DB mode: nothing to write to
  try {
    const insforge = getInsForgeAdmin();
    await insforge.database.from("audit_log").insert([
      {
        action: entry.action,
        resource: entry.resource,
        resource_id: entry.resource_id ?? null,
        actor_id: entry.actor_id ?? null,
        actor_clinic: entry.actor_clinic ?? null,
        allowed: entry.allowed ?? true,
        detail: entry.detail ?? null,
      },
    ]);
  } catch (err) {
    // Surface the gap without leaking PHI; never throw into the request path.
    console.error(
      JSON.stringify({
        level: "error",
        event: "audit.write_failed",
        resource: entry.resource,
        action: entry.action,
        error: err instanceof Error ? err.message : String(err),
      })
    );
  }
}
