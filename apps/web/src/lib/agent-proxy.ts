/**
 * Proxy to the canonical Python agent service (ticket 0025, ADR 0013).
 *
 * The Python ReAct agent (`apps/agent/`) is the sole agent implementation.
 * All `/api/run` and `/api/stream` traffic routes through these helpers.
 *
 * Service-to-service auth uses `AGENT_SERVICE_TOKEN` (ticket 0005). The
 * `X-Request-ID` is forwarded for distributed tracing (ticket 0021).
 *
 * Server-only.
 */
import { log } from "./logging";

function agentBaseUrl(): string {
  return (process.env.AGENT_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

function authHeaders(requestId?: string): Record<string, string> {
  const h: Record<string, string> = {};
  const token = process.env.AGENT_SERVICE_TOKEN?.trim();
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (requestId) {
    h["X-Request-ID"] = requestId;
    // W3C trace context so the agent joins the same trace (ticket 0021).
    h["traceparent"] = `00-${requestId.replace(/-/g, "").padEnd(32, "0").slice(0, 32)}-${requestId
      .replace(/-/g, "")
      .padEnd(16, "0")
      .slice(0, 16)}-01`;
  }
  return h;
}

/** Enqueue a run on the agent (uploads the real PDF). Returns the run id. */
export async function proxyRun(
  pdf: Blob,
  filename: string,
  clinicId: string,
  requestId?: string
): Promise<{ run_id: string; status: string }> {
  const form = new FormData();
  form.set("pdf", pdf, filename);
  form.set("clinic_id", clinicId);
  const res = await fetch(`${agentBaseUrl()}/api/run`, {
    method: "POST",
    headers: authHeaders(requestId),
    body: form,
  });
  if (!res.ok) {
    log.error("agent_proxy.run_failed", { status: res.status, request_id: requestId });
    throw new Error(`agent /api/run returned ${res.status}`);
  }
  return (await res.json()) as { run_id: string; status: string };
}

/** Proxy the agent's SSE stream for a run, forwarding the trace id. */
export async function proxyStream(runId: string, requestId?: string): Promise<Response> {
  const res = await fetch(`${agentBaseUrl()}/api/stream/${runId}`, {
    headers: { ...authHeaders(requestId), Accept: "text/event-stream" },
  });
  return res;
}

/** Fetch durable run detail from the agent (DB-backed; ticket 0028). */
export async function proxyRunDetail(runId: string, requestId?: string): Promise<unknown | null> {
  const res = await fetch(`${agentBaseUrl()}/api/run/${runId}`, { headers: authHeaders(requestId) });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`agent /api/run/${runId} returned ${res.status}`);
  return await res.json();
}
