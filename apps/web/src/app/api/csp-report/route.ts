import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * CSP violation report sink (ticket 0024). Browsers POST here per the
 * `report-uri` directive. For now we log; once the observability stack
 * lands (ticket 0011) route this through the structured logger.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    console.warn("[csp-report]", JSON.stringify(body));
  } catch {
    // ignore malformed reports
  }
  return new NextResponse(null, { status: 204 });
}
