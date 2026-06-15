import { NextResponse } from "next/server";
import { getRun } from "@/lib/agent-runs";
import { proxyRunDetail } from "@/lib/agent-proxy";
import { denyIfNotOwner, getServerSession, unauthorized } from "@/lib/auth/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const { id } = await params;

  // Try local DB first (prior_auths + agent_events)
  const run = await getRun(id);
  if (run) {
    const denied = await denyIfNotOwner(session, "run", id, run.clinic_id);
    if (denied) return denied;
    return NextResponse.json(run);
  }

  // Fall back to the agent service for runs that may only exist there
  const detail = await proxyRunDetail(id, _request.headers.get("x-request-id") ?? undefined);
  if (!detail) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }

  return NextResponse.json(detail);
}
