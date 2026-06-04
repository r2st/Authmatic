import fs from "node:fs";
import path from "node:path";
import { getDemoCase, type DemoCaseId } from "../demo-cases";
import { isInsForgeConfigured, getInsForgeAdmin } from "../insforge/admin";
import type { PaFormPayload } from "../pa-types";
import {
  isTigrisConfigured,
  TIGRIS_BUCKET,
  uploadToTigris,
} from "./client";
import { log } from "../logging";

export type TigrisFileRef = { key: string; url: string };

export type RunTigrisArtifacts = {
  bucket: string;
  chart?: TigrisFileRef;
  prescription?: TigrisFileRef;
  receipt?: TigrisFileRef;
};

function readDemoPdf(filename: string): Buffer | null {
  const candidates = [
    path.join(process.cwd(), "public", "demo", filename),
    path.join(process.cwd(), "demo", "pdfs", filename),
    path.join(process.cwd(), "..", "..", "demo", "pdfs", filename),
  ];

  for (const filePath of candidates) {
    try {
      if (fs.existsSync(filePath)) return fs.readFileSync(filePath);
    } catch {
      /* try next path */
    }
  }
  return null;
}

/** Upload patient PDFs to Tigris under runs/{runId}/ */
export async function uploadRunPdfs(
  runId: string,
  caseId?: DemoCaseId | string | null
): Promise<RunTigrisArtifacts | null> {
  if (!isTigrisConfigured()) return null;

  const pdfs = getDemoCase(caseId).pdfs;
  const artifacts: RunTigrisArtifacts = { bucket: TIGRIS_BUCKET };

  for (const [field, filename] of [
    ["chart", pdfs.chart],
    ["prescription", pdfs.prescription],
  ] as const) {
    const body = readDemoPdf(filename);
    if (!body) continue;
    const key = `runs/${runId}/${filename}`;
    artifacts[field] = await uploadToTigris(key, body, "application/pdf");
  }

  if (!artifacts.chart && !artifacts.prescription) return null;
  return artifacts;
}

/** Upload JSON receipt artifact after adjudication */
export async function uploadRunReceipt(
  runId: string,
  receipt: Record<string, unknown>
): Promise<TigrisFileRef | null> {
  if (!isTigrisConfigured()) return null;
  const key = `runs/${runId}/receipt.json`;
  const body = Buffer.from(JSON.stringify(receipt, null, 2), "utf-8");
  return uploadToTigris(key, body, "application/json");
}

/** Finish PERSIST: receipt to Tigris + prior_auths row in InsForge */
export async function persistRunArtifacts(
  runId: string,
  params: {
    reference_id: string;
    receipt_url: string;
    form_payload: PaFormPayload;
    artifacts: RunTigrisArtifacts;
    status: string;
  }
): Promise<{ insforge_updated: boolean; artifacts: RunTigrisArtifacts }> {
  const artifacts = { ...params.artifacts };

  try {
    const receipt = await uploadRunReceipt(runId, {
      run_id: runId,
      reference_id: params.reference_id,
      receipt_url: params.receipt_url,
      status: params.status,
      patient_name: params.form_payload.patient_name,
      medication: params.form_payload.medication,
      stored_at: new Date().toISOString(),
      tigris_bucket: TIGRIS_BUCKET,
      chart_key: artifacts.chart?.key,
      prescription_key: artifacts.prescription?.key,
    });
    if (receipt) artifacts.receipt = receipt;
  } catch (err) {
    log.error("tigris.receipt_upload_failed", { error: err instanceof Error ? err.message : String(err) });
  }

  let insforge_updated = false;
  if (isInsForgeConfigured()) {
    try {
      const insforge = getInsForgeAdmin();
      const { error } = await insforge.database.from("prior_auths").upsert([
        {
          patient_name: params.form_payload.patient_name,
          drug_name: params.form_payload.medication,
          status: params.status,
          reference_id: params.reference_id,
          receipt_url: params.receipt_url,
          chart_storage_key: artifacts.chart?.key ?? null,
          chart_storage_url: artifacts.chart?.url ?? null,
          prescription_storage_key: artifacts.prescription?.key ?? null,
          prescription_storage_url: artifacts.prescription?.url ?? null,
          updated_at: new Date().toISOString(),
        },
      ]);
      insforge_updated = !error;
      if (error) log.error("insforge.prior_auths_upsert_failed", { error: error.message });
    } catch (err) {
      log.error("insforge.persist_failed", { error: err instanceof Error ? err.message : String(err) });
    }
  }

  return { insforge_updated, artifacts };
}
