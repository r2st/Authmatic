/**
 * Postgres-backed submissions persistence (direct-pg layer, db.ts).
 *
 * Used when a direct-pg connection is configured but the InsForge HTTP SDK
 * isn't — e.g. local dev against the docker Postgres, and as the durable
 * replacement for the in-memory fallback (tickets 0016/0028).
 *
 * Tenant-scoped queries: when a valid `clinic_id` UUID is provided, queries
 * use `scopedQuery` (RLS-enforced via the `authmatic_app` role + `app.clinic_id`
 * GUC). This ensures the database enforces tenant isolation even if app code
 * has a bug. The public payer portal has no clinic session, so those paths
 * fall back to the privileged `adminQuery` (documented payer-surface exception,
 * ADR 0005/0007); rows land on the backfill clinic until claimed.
 *
 * Server-only.
 */
import type { PaSubmission, PaSubmissionRow } from "@authmatic/shared";
import { adminQuery, scopedQuery } from "./db";

const DEFAULT_CLINIC = "00000000-0000-0000-0000-000000000001";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** pg returns `Date` for timestamptz; normalize to an ISO string. */
function iso(v: unknown): string | undefined {
  if (v == null) return undefined;
  return v instanceof Date ? v.toISOString() : String(v);
}

function rowToSubmission(r: PaSubmissionRow): PaSubmission {
  return {
    reference_id: r.reference_id,
    clinic_id: r.clinic_id ?? undefined,
    patient_name: r.patient_name,
    dob: r.dob,
    member_id: r.member_id,
    diagnosis: r.diagnosis,
    medication: r.medication,
    dosage: r.dosage,
    provider_name: r.provider_name,
    justification: r.justification,
    status: r.status,
    submitted_at: iso(r.submitted_at) ?? new Date().toISOString(),
    under_review_at: iso(r.under_review_at),
    decided_at: iso(r.decided_at),
    decision_notes: r.decision_notes ?? undefined,
    denial_reason: r.denial_reason ?? undefined,
    reviewer_id: r.reviewer_id ?? undefined,
  };
}

export async function pgCreateSubmission(sub: PaSubmission): Promise<PaSubmission> {
  const rows = await adminQuery<PaSubmissionRow>(
    `INSERT INTO pa_submissions
       (reference_id, clinic_id, patient_name, dob, member_id, diagnosis,
        medication, dosage, provider_name, justification, status, submitted_at)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
     RETURNING *`,
    [
      sub.reference_id,
      sub.clinic_id ?? DEFAULT_CLINIC,
      sub.patient_name,
      sub.dob,
      sub.member_id,
      sub.diagnosis,
      sub.medication,
      sub.dosage,
      sub.provider_name,
      sub.justification,
      sub.status,
      sub.submitted_at,
    ]
  );
  return rowToSubmission(rows[0]);
}

export async function pgGetSubmission(
  reference_id: string,
  clinic_id?: string
): Promise<PaSubmission | null> {
  const sql = "SELECT * FROM pa_submissions WHERE reference_id = $1 LIMIT 1";
  const params = [reference_id];
  const scoped = clinic_id && UUID_RE.test(clinic_id);
  const rows = scoped
    ? await scopedQuery<PaSubmissionRow>(clinic_id, sql, params)
    : await adminQuery<PaSubmissionRow>(sql, params);
  return rows.length ? rowToSubmission(rows[0]) : null;
}

export async function pgListSubmissions(limit: number, clinic_id?: string): Promise<PaSubmission[]> {
  // Only scope when clinic_id is a real UUID (the demo/fixture clinic ids
  // aren't); otherwise list recent unscoped via admin. When scoped, RLS
  // enforces tenant isolation; the WHERE is defense-in-depth.
  const scoped = clinic_id && UUID_RE.test(clinic_id);
  const rows = scoped
    ? await scopedQuery<PaSubmissionRow>(
        clinic_id,
        "SELECT * FROM pa_submissions WHERE clinic_id = $2 ORDER BY submitted_at DESC LIMIT $1",
        [limit, clinic_id]
      )
    : await adminQuery<PaSubmissionRow>(
        "SELECT * FROM pa_submissions ORDER BY submitted_at DESC LIMIT $1",
        [limit]
      );
  return rows.map(rowToSubmission);
}

export async function pgUpdateSubmission(
  reference_id: string,
  patch: Record<string, unknown>,
  clinic_id?: string
): Promise<PaSubmission | null> {
  const keys = Object.keys(patch);
  if (keys.length === 0) return pgGetSubmission(reference_id, clinic_id);
  const set = keys.map((k, i) => `${k} = $${i + 2}`).join(", ");
  const sql = `UPDATE pa_submissions SET ${set} WHERE reference_id = $1 RETURNING *`;
  const params = [reference_id, ...keys.map((k) => patch[k])];
  const scoped = clinic_id && UUID_RE.test(clinic_id);
  const rows = scoped
    ? await scopedQuery<PaSubmissionRow>(clinic_id, sql, params)
    : await adminQuery<PaSubmissionRow>(sql, params);
  return rows.length ? rowToSubmission(rows[0]) : null;
}
