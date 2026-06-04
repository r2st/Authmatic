/**
 * ⚠️ DEMO-ONLY — DO NOT ADD FEATURES HERE.
 *
 * This is the scripted demo pipeline (no LLM planner — it's theater).
 * Per ADR 0013 the canonical agent is the Python ReAct loop in
 * `apps/agent/`. This file is retained only as the `DEMO_FIXTURE_MODE`
 * fallback during migration (ticket 0025) and is slated for deletion
 * once `/api/run` proxies to the real agent. New agent logic goes in
 * `apps/agent/`, not here.
 *
 * See: docs/decisions/0013-canonical-agent.md
 */
import { adjudicateReference } from "./adjudication";
import {
  appendStep,
  createRun,
  getRun,
  updateRun,
  updateStep,
  type AgentStep,
} from "./agent-runs";
import { createSubmission } from "./submissions";
import { extractWithDaytona } from "./sponsors/daytona-extract";
import { verifyWithOpsera } from "./sponsors/opsera-verify";
import { submitWithRtrvr, type RtrvrResult } from "./sponsors/rtrvr-submit";
import {
  persistRunArtifacts,
  uploadRunPdfs,
  type RunTigrisArtifacts,
} from "./tigris/persist-run";
import { getDemoFormPayload, submissionPath, type DemoCaseId } from "./demo-cases";
import type { PaFormPayload } from "./pa-types";

const pipelines = new Set<string>();

function baseUrl() {
  if (process.env.WEB_URL?.trim()) return process.env.WEB_URL.trim();
  if (process.env.VERCEL_URL?.trim()) {
    return `https://${process.env.VERCEL_URL.trim()}`;
  }
  return "http://localhost:3000";
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function emitStep(
  runId: string,
  step: Omit<AgentStep, "status"> & { status?: AgentStep["status"] },
  onEvent: (data: Record<string, unknown>) => void,
  minMs = 1200
) {
  const started = Date.now();
  const full: AgentStep = { ...step, status: step.status ?? "running" };
  appendStep(runId, full);
  onEvent({ type: "step", step: full, run: getRun(runId) });

  await sleep(minMs);

  const duration_ms = Date.now() - started;
  updateStep(runId, step.step_no, { status: "done", duration_ms });
  onEvent({
    type: "step",
    step: { ...full, status: "done", duration_ms },
    run: getRun(runId),
  });
}

export function isPipelineRunning(id: string): boolean {
  return pipelines.has(id);
}

export async function runAgentPipeline(
  runId: string,
  _initialPayload: PaFormPayload,
  onEvent: (data: Record<string, unknown>) => void,
  options?: { caseId?: DemoCaseId }
) {
  if (pipelines.has(runId)) return;
  pipelines.add(runId);

  const caseId = options?.caseId;
  const existing = getRun(runId);
  if (!existing) {
    createRun(runId, _initialPayload, caseId);
  } else if (caseId && !existing.case_id) {
    updateRun(runId, { case_id: caseId });
  }

  onEvent({ type: "progress", message: "Agent starting…", run: getRun(runId) });

  try {
    let tigrisArtifacts: RunTigrisArtifacts | null = null;
    const tigrisPromise = uploadRunPdfs(runId, caseId).catch(() => null);

    const extracted = await extractWithDaytona(caseId);
    const formPayload = extracted.payload;
    updateRun(runId, { form_payload: formPayload });

    tigrisArtifacts = await tigrisPromise;

    const extractOutput: Record<string, unknown> = {
      ...formPayload,
      _extract: extracted.meta,
    };
    if (tigrisArtifacts) {
      extractOutput.tigris = {
        bucket: tigrisArtifacts.bucket,
        chart: tigrisArtifacts.chart,
        prescription: tigrisArtifacts.prescription,
      };
      updateRun(runId, { tigris_artifacts: tigrisArtifacts });
    }

    await emitStep(
      runId,
      {
        step_no: 1,
        verb: "EXTRACT",
        sponsor: "Daytona",
        plan: "Parse patient chart and prescription PDFs in Daytona sandbox; extract payer fields.",
        tool_input: { patient: formPayload.patient_name, files: 2 },
        tool_output: extractOutput,
      },
      onEvent,
      // Theatrical pacing tightened so the run completes in ~10s instead of ~30s.
      // Each card still animates in cleanly; total dead time dropped from 6.0s to 3.0s.
      800
    );

    await emitStep(
      runId,
      {
        step_no: 2,
        verb: "VERIFY",
        sponsor: "Opsera",
        plan: "Opsera MCP security scan + PHI scope check before payer submit.",
        tool_input: { fields: Object.keys(formPayload) },
      },
      onEvent,
      400
    );

    const verify = await verifyWithOpsera(formPayload);
    updateStep(runId, 2, { tool_output: verify });
    onEvent({ type: "step", step: getRun(runId)!.steps[1], run: getRun(runId) });

    if (!verify.passed) {
      throw new Error(
        `Opsera compliance failed: ${verify.flagged_fields.join("; ") || verify.notes}`
      );
    }

    const portalPath = `/portal/healthfirst/prior-auth?autofill=1&run=${runId}${caseId ? `&case=${caseId}` : ""}`;
    updateRun(runId, { portal_url: portalPath });
    onEvent({ type: "portal", path: portalPath, run: getRun(runId) });

    const rtrvrPromise = submitWithRtrvr(formPayload).catch((err) => ({
      used: false as const,
      mode: "portal_autofill" as const,
      error: err instanceof Error ? err.message : "Rtrvr skipped",
    }));

    await emitStep(
      runId,
      {
        step_no: 3,
        verb: "SUBMIT",
        sponsor: "Rtrvr",
        plan: "Rtrvr Agent API fills HealthFirst portal; iframe shows live autofill.",
        tool_input: { portal_path: portalPath, fields: formPayload },
      },
      onEvent,
      600
    );

    // Race the live Rtrvr browser session against a 4s fallback to portal_autofill.
    // Was 8s — but real Rtrvr calls either land fast or land never; 4s is enough to
    // tell the difference and saves ~4s on every run that falls back.
    const rtrvr = await Promise.race<RtrvrResult>([
      rtrvrPromise,
      new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              used: false,
              mode: "portal_autofill",
              error: "Rtrvr timeout — iframe autofill",
            }),
          4000
        )
      ),
    ]);
    const submission = await createSubmission(formPayload);
    const receipt_url = submissionPath(submission.reference_id);
    const receipt_absolute = `${baseUrl()}${receipt_url}`;

    updateStep(runId, 3, {
      tool_output: {
        reference_id: rtrvr.reference_id ?? submission.reference_id,
        status: submission.status,
        receipt_url,
        rtrvr,
      },
    });
    updateRun(runId, {
      reference_id: submission.reference_id,
      receipt_url,
    });
    onEvent({ type: "step", step: getRun(runId)!.steps[2], run: getRun(runId) });

    await emitStep(
      runId,
      {
        step_no: 4,
        verb: "ADJUDICATE",
        sponsor: "HealthFirst",
        plan: "Payer medical review queue — step therapy and formulary check.",
        tool_input: { reference_id: submission.reference_id },
      },
      onEvent,
      700
    );

    // Adjudication delay tightened from 2.0s → 0.6s — still feels like a
    // payer rule engine ticking, doesn't pad the demo unnecessarily.
    const reviewMs = 600;
    const adjudication = await adjudicateReference(submission.reference_id, reviewMs);
    // A failed/missing adjudication must NEVER present as an approval — that
    // would tell a clinic a PA was granted when no decision was reached.
    // Surface it as a run error; the submission stays at its real DB status
    // (pending_review / under_review). See docs/decisions/0015-adjudication-scope.md.
    if (!adjudication) {
      throw new Error(
        `Adjudication did not complete for ${submission.reference_id}; ` +
          `submission remains pending payer review`
      );
    }
    const finalStatus = adjudication.status;

    updateStep(runId, 4, {
      tool_output: {
        reference_id: submission.reference_id,
        status: finalStatus,
        review_delay_ms: reviewMs,
        denial_reason: adjudication?.denial_reason,
      },
    });

    const runBeforePersist = getRun(runId)!;
    const baseArtifacts: RunTigrisArtifacts = runBeforePersist.tigris_artifacts ?? {
      bucket: process.env.TIGRIS_BUCKET ?? "authmatic-demo",
    };

    // Emit the PERSIST card optimistically so the user sees "Done" the moment
    // the receipt is ready. The actual Tigris upload + prior_auths upsert run
    // in the background and back-fill the card via a second SSE event when they
    // complete. Cuts perceived wall-clock by another ~1-2s.
    await emitStep(
      runId,
      {
        step_no: 5,
        verb: "PERSIST",
        sponsor: "InsForge + Tigris",
        plan: "Store workflow in InsForge; PDFs and receipt in Tigris.",
        tool_output: {
          insforge: "pa_submissions (submit step)",
          tigris_bucket: baseArtifacts.bucket,
          reference_id: submission.reference_id,
        },
      },
      onEvent,
      500
    );

    updateRun(runId, { status: "completed" });
    onEvent({ type: "done", run: getRun(runId) });

    // Fire-and-forget heavy persistence — don't block the response.
    void persistRunArtifacts(runId, {
      reference_id: submission.reference_id,
      receipt_url: receipt_absolute,
      form_payload: formPayload,
      artifacts: baseArtifacts,
      status: finalStatus,
    })
      .then(({ insforge_updated, artifacts }) => {
        updateRun(runId, { tigris_artifacts: artifacts });
        updateStep(runId, 5, {
          tool_output: {
            insforge: insforge_updated
              ? "prior_auths + pa_submissions"
              : "pa_submissions (submit step)",
            tigris_bucket: artifacts.bucket,
            chart: artifacts.chart,
            prescription: artifacts.prescription,
            receipt: artifacts.receipt,
            reference_id: submission.reference_id,
          },
        });
        onEvent({ type: "step", step: getRun(runId)!.steps[4], run: getRun(runId) });
      })
      .catch((err) => {
        console.error("[persist] background failed:", err);
      });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Agent run failed";
    updateRun(runId, { status: "error", error: message });
    onEvent({ type: "error", message, run: getRun(runId) });
  } finally {
    pipelines.delete(runId);
  }
}

export function defaultPayload(caseId?: DemoCaseId): PaFormPayload {
  return getDemoFormPayload(caseId);
}
