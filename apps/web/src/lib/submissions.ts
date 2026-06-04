import type { PaFormPayload, PaSubmission, PaSubmissionRow } from "@authmatic/shared";
import { getInsForgeAdmin, isInsForgeConfigured } from "./insforge/admin";
import { auditLog } from "./audit";
import { newReferenceId } from "./reference-id";

type DbRow = PaSubmissionRow;

const memory = new Map<string, PaSubmission>();

function rowToSubmission(row: DbRow): PaSubmission {
  return {
    reference_id: row.reference_id,
    clinic_id: row.clinic_id ?? undefined,
    patient_name: row.patient_name,
    dob: row.dob,
    member_id: row.member_id,
    diagnosis: row.diagnosis,
    medication: row.medication,
    dosage: row.dosage,
    provider_name: row.provider_name,
    justification: row.justification,
    status: row.status,
    submitted_at: row.submitted_at,
    under_review_at: row.under_review_at ?? undefined,
    decided_at: row.decided_at ?? undefined,
    decision_notes: row.decision_notes ?? undefined,
    denial_reason: row.denial_reason ?? undefined,
    reviewer_id: row.reviewer_id ?? undefined,
  };
}

function saveLocal(submission: PaSubmission): PaSubmission {
  memory.set(submission.reference_id, submission);
  return submission;
}

export async function createSubmission(
  payload: PaFormPayload,
  clinic_id?: string
): Promise<PaSubmission> {
  const reference_id = newReferenceId();
  const submitted_at = new Date().toISOString();
  const submission: PaSubmission = {
    ...payload,
    reference_id,
    clinic_id,
    status: "pending_review",
    submitted_at,
  };

  void auditLog({ action: "create", resource: "pa_submission", resource_id: reference_id, actor_clinic: clinic_id });

  if (!isInsForgeConfigured()) {
    return saveLocal(submission);
  }

  try {
    const insforge = getInsForgeAdmin();
    // clinic_id column is added by ticket 0006's migration; include it so
    // tenancy is recorded as soon as that migration is applied.
    const { data, error } = await insforge.database
      .from("pa_submissions")
      .insert([{ reference_id, clinic_id, ...payload, status: "pending_review", submitted_at }])
      .select("*");

    if (error) throw new Error(error.message);
    return rowToSubmission(data![0] as DbRow);
  } catch {
    return saveLocal(submission);
  }
}

export async function getSubmission(reference_id: string): Promise<PaSubmission | null> {
  // Audit every read of a PHI resource (ADR 0008). Actor identity is
  // threaded from the session by ticket 0005; null until then.
  void auditLog({ action: "read", resource: "pa_submission", resource_id: reference_id });

  if (memory.has(reference_id)) {
    return memory.get(reference_id) ?? null;
  }

  if (!isInsForgeConfigured()) return null;

  try {
    const insforge = getInsForgeAdmin();
    const { data, error } = await insforge.database
      .from("pa_submissions")
      .select("*")
      .eq("reference_id", reference_id)
      .limit(1);

    if (error) throw new Error(error.message);
    if (!data?.length) return null;
    return rowToSubmission(data[0] as DbRow);
  } catch {
    return memory.get(reference_id) ?? null;
  }
}

export async function updateSubmission(
  reference_id: string,
  patch: Partial<PaSubmission>
): Promise<PaSubmission | null> {
  const local = memory.get(reference_id);
  if (local) {
    const updated = { ...local, ...patch };
    memory.set(reference_id, updated);
    return updated;
  }

  if (!isInsForgeConfigured()) return null;

  try {
    const insforge = getInsForgeAdmin();
    const { data, error } = await insforge.database
      .from("pa_submissions")
      .update(patch)
      .eq("reference_id", reference_id)
      .select("*");

    if (error) throw new Error(error.message);
    if (!data?.length) return null;
    return rowToSubmission(data[0] as DbRow);
  } catch {
    return null;
  }
}

/** List submissions, scoped to one clinic when `clinic_id` is given (tenancy). */
export async function listSubmissions(limit = 20, clinic_id?: string): Promise<PaSubmission[]> {
  if (isInsForgeConfigured()) {
    try {
      const insforge = getInsForgeAdmin();
      let query = insforge.database
        .from("pa_submissions")
        .select("*")
        .order("submitted_at", { ascending: false })
        .limit(limit);
      if (clinic_id) query = query.eq("clinic_id", clinic_id);
      const { data, error } = await query;

      if (!error && data?.length) {
        return data.map((row) => rowToSubmission(row as DbRow));
      }
    } catch {
      /* fall through */
    }
  }

  return [...memory.values()]
    .filter((s) => (clinic_id ? s.clinic_id === clinic_id : true))
    .sort((a, b) => b.submitted_at.localeCompare(a.submitted_at))
    .slice(0, limit);
}

export { isInsForgeConfigured };
