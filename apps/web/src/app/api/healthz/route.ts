import { NextResponse } from "next/server";
import { APP_ENV, APP_VERSION } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Liveness probe (ticket 0015). Returns 200 if the process is up. Does no
 * dependency checks — use /api/readyz for those. Restart-trigger for the
 * orchestrator.
 */
export async function GET() {
  return NextResponse.json({ status: "ok", env: APP_ENV, version: APP_VERSION });
}
