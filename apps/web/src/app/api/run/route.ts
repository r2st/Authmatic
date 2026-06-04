import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { defaultPayload, runAgentPipeline } from "@/lib/agent-orchestrator";
import { createRun } from "@/lib/agent-runs";
import { BATCH_DEMO_IDS, DEMO_CASES, getDemoCase, LIVE_BATCH_IDS, type DemoCaseId } from "@/lib/demo-cases";
import { createBatch } from "@/lib/batch-runs";
import { getServerSession, unauthorized } from "@/lib/auth/server";
import { hashBody, lookupIdempotency, saveIdempotency } from "@/lib/idempotency";
import { isPythonAgentEnabled, proxyRun } from "@/lib/agent-proxy";

function parseCaseId(raw: unknown): DemoCaseId | undefined {
  if (typeof raw !== "string" || !(raw in DEMO_CASES)) return undefined;
  return raw as DemoCaseId;
}

export async function POST(request: Request) {
  // Clinic-facing: starting an agent run files a real PA. Requires a session.
  const session = await getServerSession();
  if (!session) return unauthorized();

  const runId = randomUUID();
  const requestId = request.headers.get("x-request-id") ?? undefined;
  const contentType = request.headers.get("content-type") ?? "";

  let demo = true;
  let caseId: DemoCaseId | undefined;

  if (contentType.includes("multipart/form-data")) {
    const form = await request.formData();
    const chart = form.get("chart");
    // Canonical path (ticket 0025/0029): a real uploaded chart goes to the
    // Python agent, which extracts the ACTUAL document — never a caseId
    // fixture. Returns the agent's queued run id.
    if (isPythonAgentEnabled() && chart instanceof Blob) {
      const filename = (chart as File).name || "chart.pdf";
      const result = await proxyRun(chart, filename, session.clinic_id, requestId);
      return NextResponse.json({ ...result, demo: false, via: "python-agent" });
    }
    demo = form.get("demo") === "true" || !chart;
    caseId = parseCaseId(form.get("case_id"));
  } else if (contentType.includes("application/json")) {
    const body = (await request.json().catch(() => ({}))) as {
      demo?: boolean;
      case_id?: string;
      batch?: boolean;
      case_ids?: string[];
    };

    if (body.batch && Array.isArray(body.case_ids)) {
      return startBatch(body.case_ids, session.clinic_id);
    }

    demo = body.demo !== false;
    caseId = parseCaseId(body.case_id);
  }

  // Idempotency (ticket 0017): a double-clicked "Run" with the same
  // Idempotency-Key + same intent returns the original run instead of
  // starting a second agent loop (two Rtrvr submissions). Scoped per clinic.
  const idemKey = request.headers.get("Idempotency-Key");
  const idemFingerprint = hashBody({ caseId: caseId ?? null, demo });
  if (idemKey) {
    const prior = lookupIdempotency(idemKey, session.clinic_id, idemFingerprint);
    if (prior.kind === "conflict") {
      return NextResponse.json(
        { error: "idempotency_conflict", message: "Idempotency-Key reused with a different request." },
        { status: 422 }
      );
    }
    if (prior.kind === "replay") {
      return NextResponse.json(prior.body, { status: prior.status });
    }
  }

  const form_payload = defaultPayload(caseId);
  createRun(runId, form_payload, caseId, session.clinic_id);

  void runAgentPipeline(runId, form_payload, () => {}, { caseId });

  const demoCase = getDemoCase(caseId);

  const responseBody = {
    run_id: runId,
    case_id: caseId ?? "sarah-martinez",
    demo,
    message: demo
      ? `Demo run started — ${demoCase.title}: ${demoCase.payload.patient_name}`
      : "Run started",
  };
  if (idemKey) saveIdempotency(idemKey, session.clinic_id, idemFingerprint, 200, responseBody);
  return NextResponse.json(responseBody);
}

function startBatch(caseIds: string[], clinicId: string) {
  const batchId = randomUUID();
  const validIds = caseIds.filter((id) => id in DEMO_CASES) as DemoCaseId[];
  const ids = validIds.length ? validIds : LIVE_BATCH_IDS;

  const runIds = ids.map(() => randomUUID());

  ids.forEach((caseId, i) => {
    const runId = runIds[i];
    const form_payload = defaultPayload(caseId);
    createRun(runId, form_payload, caseId, clinicId);
    void runAgentPipeline(runId, form_payload, () => {}, { caseId });
  });

  createBatch(batchId, ids, runIds, clinicId);

  return NextResponse.json({
    batch_id: batchId,
    run_ids: runIds,
    case_ids: ids,
    message: `Batch started — ${ids.length} patients in parallel`,
  });
}

export async function GET() {
  // Lists demo case templates (no PHI), but still clinic-only.
  const session = await getServerSession();
  if (!session) return unauthorized();
  return NextResponse.json({
    cases: Object.values(DEMO_CASES).map((c) => ({
      id: c.id,
      title: c.title,
      blurb: c.blurb,
      patient: c.payload.patient_name,
      medication: c.payload.medication,
      expect: c.expect,
    })),
    batch_default: BATCH_DEMO_IDS,
  });
}
