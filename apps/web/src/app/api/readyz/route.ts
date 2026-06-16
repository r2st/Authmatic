import { NextResponse } from "next/server";
import { HeadBucketCommand } from "@aws-sdk/client-s3";
import { APP_ENV, APP_VERSION } from "@/lib/env";
import { getInsForgeAdmin, isInsForgeConfigured } from "@/lib/insforge/admin";
import {
  getTigrisClient,
  isTigrisConfigured,
  TIGRIS_BUCKET,
} from "@/lib/tigris/client";

export const dynamic = "force-dynamic";

type DepState = "ok" | "down" | "not_configured";

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`timeout after ${ms}ms`)), ms)
    ),
  ]);
}

async function checkInsForge(): Promise<DepState> {
  if (!isInsForgeConfigured()) return "not_configured";
  try {
    const insforge = getInsForgeAdmin();
    const { error } = await withTimeout(
      (async () =>
        insforge.database
          .from("pa_submissions")
          .select("reference_id")
          .limit(1))(),
      2500
    );
    return error ? "down" : "ok";
  } catch {
    return "down";
  }
}

async function checkTigris(): Promise<DepState> {
  if (!isTigrisConfigured()) return "not_configured";
  try {
    await withTimeout(
      getTigrisClient().send(new HeadBucketCommand({ Bucket: TIGRIS_BUCKET })),
      2500
    );
    return "ok";
  } catch {
    return "down";
  }
}

/**
 * Readiness probe (ticket 0015). 503 if any required dependency is down so
 * the load balancer stops routing traffic to a running-but-broken instance.
 */
export async function GET() {
  const [insforge, tigris] = await Promise.all([checkInsForge(), checkTigris()]);
  const deps = { insforge, tigris };
  const down = Object.values(deps).some((s) => s === "down");

  return NextResponse.json(
    {
      status: down ? "degraded" : "ok",
      env: APP_ENV,
      version: APP_VERSION,
      deps,
    },
    { status: down ? 503 : 200 }
  );
}
