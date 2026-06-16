import { NextResponse } from "next/server";
import { BATCH_DEMO_IDS, DEMO_CASES, getDemoCase, getDemoFormPayload, LIVE_BATCH_IDS, type DemoCaseId } from "@/lib/demo-cases";
import { getServerSession, unauthorized } from "@/lib/auth/server";
import { hashBody, lookupIdempotency, saveIdempotency } from "@/lib/idempotency";
import { proxyRun } from "@/lib/agent-proxy";

function parseCaseId(raw: unknown): DemoCaseId | undefined {
  if (typeof raw !== "string" || !(raw in DEMO_CASES)) return undefined;
  return raw as DemoCaseId;
}

export async function POST(request: Request) {
  // Clinic-facing: starting an agent run files a real PA. Requires a session.
  const session = await getServerSession();
  if (!session) return unauthorized();

  const requestId = request.headers.get("x-request-id") ?? undefined;
  const contentType = request.headers.get("content-type") ?? "";

  let caseId: DemoCaseId | undefined;

  if (contentType.includes("multipart/form-data")) {
    const form = await request.formData();
    const chart = form.get("chart");

    // All uploaded charts go to the Python agent for real extraction.
    if (chart instanceof Blob) {
      const filename = (chart as File).name || "chart.pdf";
      const result = await proxyRun(chart, filename, session.clinic_id, requestId);
      return NextResponse.json({ ...result, demo: false, via: "python-agent" });
    }

    // No chart uploaded — use a demo case to seed the agent
    caseId = parseCaseId(form.get("case_id"));
  } else if (contentType.includes("application/json")) {
    const body = (await request.json().catch(() => ({}))) as {
      case_id?: string;
      batch?: boolean;
      case_ids?: string[];
    };

    if (body.batch && Array.isArray(body.case_ids)) {
      return startBatch(body.case_ids, session.clinic_id, requestId);
    }

    caseId = parseCaseId(body.case_id);
  }

  // Idempotency (ticket 0017): a double-clicked "Run" with the same
  // Idempotency-Key + same intent returns the original run instead of
  // starting a second agent loop. Scoped per clinic.
  const idemKey = request.headers.get("Idempotency-Key");
  const idemFingerprint = hashBody({ caseId: caseId ?? null });
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

  // Build a synthetic PDF from the demo case payload and send it to the
  // Python agent. If no chart is available, proxy with an empty blob so
  // the agent can still seed from its own demo fixture data.
  const demoCase = getDemoCase(caseId);
  const payload = getDemoFormPayload(caseId);
  const syntheticBlob = new Blob([JSON.stringify(payload)], { type: "application/json" });
  const result = await proxyRun(syntheticBlob, "demo-case.json", session.clinic_id, requestId);

  const responseBody = {
    ...result,
    case_id: caseId ?? "sarah-martinez",
    demo: true,
    via: "python-agent",
    message: `Demo run started — ${demoCase.title}: ${demoCase.payload.patient_name}`,
  };
  if (idemKey) saveIdempotency(idemKey, session.clinic_id, idemFingerprint, 200, responseBody);
  return NextResponse.json(responseBody);
}

async function startBatch(caseIds: string[], clinicId: string, requestId?: string) {
  const validIds = caseIds.filter((id) => id in DEMO_CASES) as DemoCaseId[];
  const ids = validIds.length ? validIds : LIVE_BATCH_IDS;

  const results = await Promise.all(
    ids.map(async (caseId) => {
      const payload = getDemoFormPayload(caseId);
      const syntheticBlob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      const result = await proxyRun(syntheticBlob, `demo-${caseId}.json`, clinicId, requestId);
      return { case_id: caseId, ...result };
    })
  );

  return NextResponse.json({
    run_ids: results.map((r) => r.run_id),
    case_ids: ids,
    via: "python-agent",
    message: `Batch started — ${ids.length} patients in parallel`,
    runs: results,
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
