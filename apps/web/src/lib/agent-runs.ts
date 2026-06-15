/**
 * Agent run state backed by the `prior_auths` + `agent_events` tables.
 *
 * Previously this module used a `globalThis` in-memory Map that was lost
 * on restart and diverged across instances. Now it reads durable state
 * from Postgres (via db.ts). The Python agent writes to these tables;
 * this module is read-only from the web side.
 *
 * The type interfaces (AgentRun, AgentStep, RunStatus) are preserved so
 * existing consumers (components, API routes) continue to compile.
 *
 * Server-only.
 */
import type { PaFormPayload } from "./pa-types";
import { adminQuery, isPgConfigured, scopedQuery } from "./db";
import { log } from "./logging";

export type RunStatus = "running" | "completed" | "error";

export interface AgentStep {
  step_no: number;
  verb: string;
  sponsor: string;
  plan: string;
  status: "pending" | "running" | "done" | "error";
  tool_input?: Record<string, unknown>;
  tool_output?: Record<string, unknown>;
  duration_ms?: number;
}

export interface TigrisArtifacts {
  bucket: string;
  chart?: { key: string; url: string };
  prescription?: { key: string; url: string };
  receipt?: { key: string; url: string };
}

export interface AgentRun {
  id: string;
  status: RunStatus;
  clinic_id?: string;
  case_id?: string;
  form_payload: PaFormPayload;
  reference_id?: string;
  receipt_url?: string;
  portal_url?: string;
  tigris_artifacts?: TigrisArtifacts;
  steps: AgentStep[];
  created_at: string;
  error?: string;
}

// ── DB row shapes ────────────────────────────────────────────────────

interface PriorAuthRow {
  id: string;
  patient_id: string;
  clinic_id: string;
  drug_name: string;
  drug_ndc: string | null;
  dose: string | null;
  diagnosis_code: string | null;
  status: string;
  receipt_url: string | null;
  trigger_pdf_key: string | null;
  rationale: string | null;
  created_at: Date | string;
  updated_at: Date | string;
}

interface AgentEventRow {
  id: string;
  pa_id: string;
  step_no: number;
  verb: string;
  plan: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: Record<string, unknown> | null;
  duration_ms: number | null;
  created_at: Date | string;
}

// ── Helpers ──────────────────────────────────────────────────────────

function iso(v: unknown): string {
  if (v instanceof Date) return v.toISOString();
  return String(v ?? new Date().toISOString());
}

function mapStatus(dbStatus: string): RunStatus {
  switch (dbStatus) {
    case "pending":
    case "submitted":
      return "running";
    case "approved":
    case "denied":
      return "completed";
    case "error":
      return "error";
    default:
      return "running";
  }
}

function rowToStep(row: AgentEventRow): AgentStep {
  return {
    step_no: row.step_no,
    verb: row.verb,
    sponsor: (row.tool_output as Record<string, unknown>)?.sponsor as string ?? row.verb,
    plan: row.plan ?? "",
    status: "done",
    tool_input: row.tool_input ?? undefined,
    tool_output: row.tool_output ?? undefined,
    duration_ms: row.duration_ms ?? undefined,
  };
}

function rowToRun(row: PriorAuthRow, steps: AgentStep[]): AgentRun {
  return {
    id: row.id,
    status: mapStatus(row.status),
    clinic_id: row.clinic_id ?? undefined,
    form_payload: {
      patient_name: "",
      dob: "",
      member_id: "",
      diagnosis: row.diagnosis_code ?? "",
      medication: row.drug_name,
      dosage: row.dose ?? "",
      provider_name: "",
      justification: row.rationale ?? "",
    },
    reference_id: undefined,
    receipt_url: row.receipt_url ?? undefined,
    steps,
    created_at: iso(row.created_at),
  };
}

// ── Public API ───────────────────────────────────────────────────────

/**
 * Get a single run by id. Uses the admin connection (the caller's route
 * is responsible for the ownership check via denyIfNotOwner).
 */
export async function getRun(id: string): Promise<AgentRun | undefined> {
  if (!isPgConfigured()) return undefined;
  try {
    const rows = await adminQuery<PriorAuthRow>(
      "SELECT * FROM prior_auths WHERE id = $1 LIMIT 1",
      [id]
    );
    if (!rows.length) return undefined;

    const eventRows = await adminQuery<AgentEventRow>(
      "SELECT * FROM agent_events WHERE pa_id = $1 ORDER BY step_no",
      [id]
    );
    return rowToRun(rows[0], eventRows.map(rowToStep));
  } catch (err) {
    log.error("agent_runs.get_failed", {
      run_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return undefined;
  }
}

/**
 * List runs, optionally scoped to one clinic (ticket 0005 tenancy).
 * When clinic_id is provided AND looks like a UUID, uses the RLS-scoped
 * connection; otherwise falls back to the admin query.
 */
export async function listRuns(limit = 20, clinic_id?: string): Promise<AgentRun[]> {
  if (!isPgConfigured()) return [];
  try {
    const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const scoped = clinic_id && UUID_RE.test(clinic_id);

    const rows = scoped
      ? await scopedQuery<PriorAuthRow>(
          clinic_id,
          "SELECT * FROM prior_auths ORDER BY created_at DESC LIMIT $1",
          [limit]
        )
      : await adminQuery<PriorAuthRow>(
          "SELECT * FROM prior_auths ORDER BY created_at DESC LIMIT $1",
          [limit]
        );

    // Batch-fetch all steps for these runs in one query
    if (!rows.length) return [];
    const runIds = rows.map((r) => r.id);
    const eventRows = await adminQuery<AgentEventRow>(
      `SELECT * FROM agent_events WHERE pa_id = ANY($1) ORDER BY pa_id, step_no`,
      [runIds]
    );

    const stepsByRun = new Map<string, AgentStep[]>();
    for (const e of eventRows) {
      const list = stepsByRun.get(e.pa_id) ?? [];
      list.push(rowToStep(e));
      stepsByRun.set(e.pa_id, list);
    }

    return rows.map((r) => rowToRun(r, stepsByRun.get(r.id) ?? []));
  } catch (err) {
    log.error("agent_runs.list_failed", {
      error: err instanceof Error ? err.message : String(err),
    });
    return [];
  }
}
