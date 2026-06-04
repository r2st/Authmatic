import { NextResponse } from "next/server";
import { getRun } from "@/lib/agent-runs";
import { denyIfNotOwner, getServerSession, unauthorized } from "@/lib/auth/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const { id } = await params;
  const run = getRun(id);
  if (!run) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }
  const denied = await denyIfNotOwner(session, "run", id, run.clinic_id);
  if (denied) return denied;

  return NextResponse.json(run);
}
