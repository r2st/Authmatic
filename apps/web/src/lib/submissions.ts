import type {
  PaFormPayload,
  PaStatus,
  PaSubmission,
  PaSubmissionRow,
} from "@authmatic/shared";
import { getInsForgeAdmin, isInsForgeConfigured } from "./insforge/admin";
import { auditLog } from "./audit";
import { newReferenceId } from "./reference-id";
import { isDemoFixtureMode } from "./demo-mode";
import { log } from "./logging";
import { isPgConfigured } from "./db";
import {
  pgCreateSubmission,
  pgGetSubmission,
  pgListSubmissions,
  pgUpdateSubmission,
} from "./submissions-pg";

/** Prefer the durable direct-pg path when configured and the SDK is not. */
function usePg(): boolean {
  return isPgConfigured() && !isInsForgeConfigured();
}

type DbRow = PaSubmissionRow;

/**
 * Thrown when persistence is unavailable (DB error, or DB unconfigured
 * outside fixture mode). Routes map this to 503 (ticket 0016) — the old
 * behavior silently fell back to an in-memory Map, masking DB outages,
 * losing data on restart, and diverging across instances.
 */
export class PersistenceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PersistenceError";
  }
}

// The in-memory store is now ONLY a fixture-mode convenience (ticket 0016):
// used solely when DEMO_FIXTURE_MODE is on, which ticket 0019 gates to
// non-prod. With a real backend configured, every path goes to InsForge and a
// failure throws PersistenceError instead of silently writing to memory.
const memory = new Map<string, PaSubmission>();

function memoryAllowed(): boolean {
  return isDemoFixtureMode();
}

// ── Patch allowlist (ticket 0018) ─────────────────────────────────────
// updateSubmission must NOT accept an arbitrary Partial<PaSubmission> — that
// let any caller rewrite member_id, submitted_at, patient identity, etc.
// Only the adjudication-lifecycle fields below are mutable; everything else
// (identity, clinical fields, reference_id, clinic_id, submitted_at) is frozen
// after creation. Unknown keys are dropped at runtime, not just at the type.
const MUTABLE_FIELDS = [
  "status",
  "under_review_at",
  "decided_at",
  "decision_notes",
  "denial_reason",
  "reviewer_id",
] as const;

export type SubmissionPatch = Partial<
  Pick<PaSubmission, (typeof MUTABLE_FIELDS)[number]>
>;

// Forward-only status machine. approved/denied are terminal; reopening is a
// deliberate, separate operation, not a raw patch.
const ALLOWED_TRANSITIONS: Record<PaStatus, readonly PaStatus[]> = {
  pending_review: ["under_review", "approved", "denied", "needs_info"],
  under_review: ["approved", "denied", "needs_info"],
  needs_info: ["under_review", "pending_review", "approved", "denied"],
  approved: [],
  denied: [],
  submitted: [], // terminal (legacy agent path)
};

export class InvalidSubmissionPatchError extends Error {}

function sanitizePatch(patch: SubmissionPatch): SubmissionPatch {
  const clean: SubmissionPatch = {};
  for (const key of MUTABLE_FIELDS) {
    if (patch[key] !== undefined) {
      (clean as Record<string, unknown>)[key] = patch[key];
    }
  }
  return clean;
}

function assertTransition(from: PaStatus, to: PaStatus): void {
  if (from === to) return;
  if (!ALLOWED_TRANSITIONS[from].includes(to)) {
    throw new InvalidSubmissionPatchError(
      `Illegal status transition ${from} → ${to}`
    );
  }
}

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

  // Durable direct-pg path (db.ts) — used when pg is configured but the
  // InsForge SDK isn't (local dev, and the durable replacement for the
  // in-memory fallback, tickets 0016/0028).
  if (usePg()) {
    try {
      return await pgCreateSubmission(submission);
    } catch (err) {
      log.error("submission.create_failed", { reference_id, error: err instanceof Error ? err.message : String(err) });
      throw new PersistenceError("Failed to persist submission");
    }
  }

  if (!isInsForgeConfigured()) {
    if (memoryAllowed()) return saveLocal(submission);
    throw new PersistenceError("Persistence unavailable: InsForge not configured");
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
  } catch (err) {
    // Fail loud — never silently drop a PA into memory (ticket 0016).
    log.error("submission.create_failed", {
      reference_id,
      error: err instanceof Error ? err.message : String(err),
    });
    throw new PersistenceError("Failed to persist submission");
  }
}

export async function getSubmission(reference_id: string, clinic_id?: string): Promise<PaSubmission | null> {
  // Audit every read of a PHI resource (ADR 0008). Actor identity is
  // threaded from the session by ticket 0005; null until then.
  void auditLog({ action: "read", resource: "pa_submission", resource_id: reference_id, actor_clinic: clinic_id });

  if (usePg()) {
    try {
      return await pgGetSubmission(reference_id, clinic_id);
    } catch (err) {
      log.error("submission.read_failed", { reference_id, error: err instanceof Error ? err.message : String(err) });
      throw new PersistenceError("Failed to read submission");
    }
  }

  if (memoryAllowed() && memory.has(reference_id)) {
    return memory.get(reference_id) ?? null;
  }

  if (!isInsForgeConfigured()) {
    if (memoryAllowed()) return memory.get(reference_id) ?? null;
    throw new PersistenceError("Persistence unavailable: InsForge not configured");
  }

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
  } catch (err) {
    log.error("submission.read_failed", {
      reference_id,
      error: err instanceof Error ? err.message : String(err),
    });
    throw new PersistenceError("Failed to read submission");
  }
}

export async function updateSubmission(
  reference_id: string,
  patch: SubmissionPatch,
  clinic_id?: string
): Promise<PaSubmission | null> {
  // Drop any non-allowlisted keys before they can reach the DB (ticket 0018).
  const clean = sanitizePatch(patch);

  // Validate the status transition against the current record. Throws
  // InvalidSubmissionPatchError on an illegal move (callers map to 422).
  const current = await getSubmission(reference_id, clinic_id);
  if (!current) return null;
  if (clean.status !== undefined) {
    assertTransition(current.status, clean.status);
  }

  if (usePg()) {
    try {
      return await pgUpdateSubmission(reference_id, clean as Record<string, unknown>, clinic_id);
    } catch (err) {
      log.error("submission.update_failed", { reference_id, error: err instanceof Error ? err.message : String(err) });
      throw new PersistenceError("Failed to update submission");
    }
  }

  if (memoryAllowed()) {
    const local = memory.get(reference_id);
    if (local) {
      const updated = { ...local, ...clean };
      memory.set(reference_id, updated);
      return updated;
    }
  }

  if (!isInsForgeConfigured()) {
    throw new PersistenceError("Persistence unavailable: InsForge not configured");
  }

  try {
    const insforge = getInsForgeAdmin();
    const { data, error } = await insforge.database
      .from("pa_submissions")
      .update(clean)
      .eq("reference_id", reference_id)
      .select("*");

    if (error) throw new Error(error.message);
    if (!data?.length) return null;
    return rowToSubmission(data[0] as DbRow);
  } catch (err) {
    if (err instanceof InvalidSubmissionPatchError) throw err;
    log.error("submission.update_failed", {
      reference_id,
      error: err instanceof Error ? err.message : String(err),
    });
    throw new PersistenceError("Failed to update submission");
  }
}

/** List submissions, scoped to one clinic when `clinic_id` is given (tenancy). */
export async function listSubmissions(limit = 20, clinic_id?: string): Promise<PaSubmission[]> {
  if (usePg()) {
    try {
      return await pgListSubmissions(limit, clinic_id);
    } catch (err) {
      log.error("submission.list_failed", { error: err instanceof Error ? err.message : String(err) });
      throw new PersistenceError("Failed to list submissions");
    }
  }

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

      if (error) throw new Error(error.message);
      return (data ?? []).map((row) => rowToSubmission(row as DbRow));
    } catch (err) {
      log.error("submission.list_failed", { error: err instanceof Error ? err.message : String(err) });
      throw new PersistenceError("Failed to list submissions");
    }
  }

  if (!memoryAllowed()) {
    throw new PersistenceError("Persistence unavailable: InsForge not configured");
  }

  return [...memory.values()]
    .filter((s) => (clinic_id ? s.clinic_id === clinic_id : true))
    .sort((a, b) => b.submitted_at.localeCompare(a.submitted_at))
    .slice(0, limit);
}

export { isInsForgeConfigured };
