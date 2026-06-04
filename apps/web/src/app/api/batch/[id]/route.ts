import { NextResponse } from "next/server";
import { getRun } from "@/lib/agent-runs";
import { getBatch } from "@/lib/batch-runs";
import { getDemoCase } from "@/lib/demo-cases";
import { denyIfNotOwner, getServerSession, unauthorized } from "@/lib/auth/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const { id } = await params;
  const batch = getBatch(id);

  if (!batch) {
    return NextResponse.json({ error: "Batch not found" }, { status: 404 });
  }
  const denied = await denyIfNotOwner(session, "batch", id, batch.clinic_id);
  if (denied) return denied;

  const runs = batch.run_ids
    .map((runId) => getRun(runId))
    .filter((r): r is NonNullable<typeof r> => Boolean(r));

  const completed = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "error").length;

  return NextResponse.json({
    batch,
    runs: runs.map((r) => ({
      id: r.id,
      case_id: r.case_id,
      title: getDemoCase(r.case_id).title,
      patient_name: r.form_payload.patient_name,
      medication: r.form_payload.medication,
      status: r.status,
      reference_id: r.reference_id,
      receipt_url: r.receipt_url,
      error: r.error,
    })),
    completed,
    failed,
    total: runs.length,
    done: completed + failed === runs.length,
  });
}
