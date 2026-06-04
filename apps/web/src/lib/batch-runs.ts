import type { AgentRun } from "./agent-runs";

export interface BatchRun {
  id: string;
  clinic_id?: string; // owning clinic (ticket 0005 tenancy)
  case_ids: string[];
  run_ids: string[];
  created_at: string;
}

function store(): Map<string, BatchRun> {
  if (!globalThis.__batchRuns) {
    globalThis.__batchRuns = new Map<string, BatchRun>();
  }
  return globalThis.__batchRuns;
}

export function createBatch(
  id: string,
  case_ids: string[],
  run_ids: string[],
  clinic_id?: string
): BatchRun {
  const batch: BatchRun = {
    id,
    clinic_id,
    case_ids,
    run_ids,
    created_at: new Date().toISOString(),
  };
  store().set(id, batch);
  return batch;
}

export function getBatch(id: string): BatchRun | undefined {
  return store().get(id);
}

export function listBatches(limit = 10): BatchRun[] {
  return [...store().values()]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, limit);
}

export type BatchStatus = {
  batch: BatchRun;
  runs: AgentRun[];
  completed: number;
  failed: number;
  total: number;
};

declare global {
  // eslint-disable-next-line no-var
  var __batchRuns: Map<string, BatchRun> | undefined;
}
