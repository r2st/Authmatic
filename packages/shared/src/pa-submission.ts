/**
 * Clinic-form subdomain types. See ADR 0005 (docs/decisions/0005-data-model-boundary.md).
 *
 * `pa_submissions` is the denormalized clinic-portal row keyed by a
 * human-visible `PA-2026-NNNNN` reference id. The agent-run subdomain
 * (`patients`, `prior_auths`, `agent_events`) is modeled separately
 * and is not exported from this file.
 */

export type PaStatus =
  | "pending_review"
  | "under_review"
  | "approved"
  | "denied"
  | "needs_info";

export interface PaFormPayload {
  patient_name: string;
  dob: string;
  member_id: string;
  diagnosis: string;
  medication: string;
  dosage: string;
  provider_name: string;
  justification: string;
}

export interface PaSubmission extends PaFormPayload {
  reference_id: string;
  /** Owning clinic (tenancy, tickets 0005/0006). Optional on legacy/demo rows. */
  clinic_id?: string;
  status: PaStatus;
  submitted_at: string;
  under_review_at?: string;
  decided_at?: string;
  decision_notes?: string;
  denial_reason?: string;
  reviewer_id?: string;
}

/**
 * Wire shape of a `pa_submissions` row as returned by the InsForge
 * database client. Mirrors the column set in
 * db/migrations/0002_add_pa_submissions.sql + 0003_add_pa_submissions_review_cols.sql.
 *
 * Distinct from `PaSubmission` because the DB returns nullable strings
 * for the review-trail columns; the app-facing type narrows nulls to
 * `undefined`.
 */
export interface PaSubmissionRow {
  reference_id: string;
  clinic_id?: string | null;
  patient_name: string;
  dob: string;
  member_id: string;
  diagnosis: string;
  medication: string;
  dosage: string;
  provider_name: string;
  justification: string;
  status: PaStatus;
  submitted_at: string;
  under_review_at?: string | null;
  decided_at?: string | null;
  decision_notes?: string | null;
  denial_reason?: string | null;
  reviewer_id?: string | null;
}

export interface AdjudicationResult {
  reference_id: string;
  status: PaStatus;
  decision_notes: string;
  denial_reason?: string;
  reviewer_id: string;
}

export const FORM_FIELDS = [
  "patient_name",
  "dob",
  "member_id",
  "diagnosis",
  "medication",
  "dosage",
  "provider_name",
  "justification",
] as const satisfies readonly (keyof PaFormPayload)[];

export const STATUS_LABELS: Record<PaStatus, string> = {
  pending_review: "Pending Review",
  under_review: "Under Review",
  approved: "Approved",
  denied: "Denied",
  needs_info: "Additional Information Required",
};
