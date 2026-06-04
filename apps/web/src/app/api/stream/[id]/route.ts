import { NextResponse } from "next/server";
import { defaultPayload, isPipelineRunning, runAgentPipeline } from "@/lib/agent-orchestrator";
import { getRun } from "@/lib/agent-runs";
import { denyIfNotOwner, getServerSession, unauthorized } from "@/lib/auth/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const { id } = await params;
  const existing = getRun(id);
  if (!existing) {
    return NextResponse.json({ error: "Run not found" }, { status: 404 });
  }
  const denied = await denyIfNotOwner(session, "run", id, existing.clinic_id);
  if (denied) return denied;

  const formPayload = existing.form_payload ?? defaultPayload();

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      let closed = false;
      const send = (data: Record<string, unknown>) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch {
          closed = true;
        }
      };

      send({ type: "connected", run_id: id });

      if (!isPipelineRunning(id)) {
        void runAgentPipeline(id, formPayload, send);
      }

      let lastStepCount = 0;
      let lastStatus = "";
      let portalSent = false;

      while (!closed) {
        const run = getRun(id);
        if (run) {
          if (run.steps.length > lastStepCount) {
            for (let i = lastStepCount; i < run.steps.length; i++) {
              send({ type: "step", step: run.steps[i], run });
            }
            lastStepCount = run.steps.length;
          }
          if (run.portal_url && !portalSent) {
            portalSent = true;
            send({ type: "portal", path: run.portal_url, run });
          }
          if (run.status !== lastStatus) {
            lastStatus = run.status;
            if (run.status === "completed") {
              send({ type: "done", run });
              break;
            }
            if (run.status === "error") {
              send({ type: "error", message: run.error ?? "Run failed", run });
              break;
            }
          }
        }
        if (!isPipelineRunning(id) && run && run.status !== "running") break;
        await new Promise((r) => setTimeout(r, 300));
      }

      closed = true;
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
