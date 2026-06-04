import { NextResponse } from "next/server";
import { log } from "@/lib/logging";

export const dynamic = "force-dynamic";

/**
 * CSP violation report sink (ticket 0024). Browsers POST here per the
 * `report-uri` directive; routed through the structured logger (ticket 0011).
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    log.warn("csp.violation", { report: body });
  } catch {
    // ignore malformed reports
  }
  return new NextResponse(null, { status: 204 });
}
