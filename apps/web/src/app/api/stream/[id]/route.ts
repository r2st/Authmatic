import { getServerSession, unauthorized } from "@/lib/auth/server";
import { proxyStream } from "@/lib/agent-proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const { id } = await params;

  // All SSE streams are served by the canonical Python agent (ADR 0013).
  // The agent tails its durable DB state, so any web instance can proxy.
  const upstream = await proxyStream(id, request.headers.get("x-request-id") ?? undefined);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
