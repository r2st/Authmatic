import type { PaFormPayload } from "./pa-types";

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
  clinic_id?: string; // owning clinic (ticket 0005 tenancy); undefined for legacy/demo runs
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

function store(): Map<string, AgentRun> {
  if (!globalThis.__agentRuns) {
    globalThis.__agentRuns = new Map<string, AgentRun>();
  }
  return globalThis.__agentRuns;
}

export function createRun(
  id: string,
  form_payload: PaFormPayload,
  case_id?: string,
  clinic_id?: string
): AgentRun {
  const run: AgentRun = {
    id,
    status: "running",
    clinic_id,
    case_id,
    form_payload,
    steps: [],
    created_at: new Date().toISOString(),
  };
  store().set(id, run);
  return run;
}

export function getRun(id: string): AgentRun | undefined {
  return store().get(id);
}

/** List runs, optionally scoped to one clinic (ticket 0005 tenancy). */
export function listRuns(limit = 20, clinic_id?: string): AgentRun[] {
  return [...store().values()]
    .filter((r) => (clinic_id ? r.clinic_id === clinic_id : true))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, limit);
}

export function updateRun(id: string, patch: Partial<AgentRun>): AgentRun | undefined {
  const run = store().get(id);
  if (!run) return undefined;
  const updated = { ...run, ...patch };
  store().set(id, updated);
  return updated;
}

export function appendStep(id: string, step: AgentStep): void {
  const run = store().get(id);
  if (!run) return;
  run.steps.push(step);
  store().set(id, run);
}

export function updateStep(
  id: string,
  step_no: number,
  patch: Partial<AgentStep>
): void {
  const run = store().get(id);
  if (!run) return;
  const idx = run.steps.findIndex((s) => s.step_no === step_no);
  if (idx === -1) return;
  run.steps[idx] = { ...run.steps[idx], ...patch };
  store().set(id, run);
}

declare global {
  // eslint-disable-next-line no-var
  var __agentRuns: Map<string, AgentRun> | undefined;
}
