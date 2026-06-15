import { NextResponse } from "next/server";
import { listRuns } from "@/lib/agent-runs";
import { getServerSession, unauthorized } from "@/lib/auth/server";
import { redact } from "@/lib/phi";

export type SecurityEvent = {
  id: string;
  at: string;
  type: "opsera_verify" | "phi_block" | "login" | "tigris_persist";
  severity: "info" | "warn" | "success";
  summary: string;
  detail?: string;
  run_id?: string;
};

const SEED: SecurityEvent[] = [
  {
    id: "seed-1",
    at: new Date(Date.now() - 3600000).toISOString(),
    type: "login",
    severity: "info",
    summary: "Clinic staff signed in",
    detail: "ma@bayarea-care.com · Bay Area Primary Care",
  },
];

export async function GET() {
  const session = await getServerSession();
  if (!session) return unauthorized();

  const events: SecurityEvent[] = [...SEED];

  const runs = await listRuns(25, session.clinic_id);

  for (const run of runs) {
    const verify = run.steps.find((s) => s.verb === "VERIFY");
    if (verify) {
      const out = verify.tool_output as {
        passed?: boolean;
        source?: string;
        flagged_fields?: string[];
      };
      events.push({
        id: `verify-${run.id}`,
        at: run.created_at,
        type: out.passed ? "opsera_verify" : "phi_block",
        severity: out.passed ? "success" : "warn",
        summary: out.passed
          ? `Opsera compliance passed (${out.source ?? "rules"})`
          : `Opsera blocked submit — ${out.flagged_fields?.join(", ") ?? "PHI risk"}`,
        detail: redact("patient_name", run.form_payload.patient_name),
        run_id: run.id,
      });
    }
    if (run.tigris_artifacts?.receipt) {
      events.push({
        id: `tigris-${run.id}`,
        at: run.created_at,
        type: "tigris_persist",
        severity: "info",
        summary: `Artifacts stored in Tigris (${run.tigris_artifacts.bucket})`,
        run_id: run.id,
      });
    }
    if (run.status === "error") {
      events.push({
        id: `err-${run.id}`,
        at: run.created_at,
        type: "phi_block",
        severity: "warn",
        summary: run.error ?? "Agent run failed",
        run_id: run.id,
      });
    }
  }

  events.sort((a, b) => b.at.localeCompare(a.at));

  return NextResponse.json({ events: events.slice(0, 40) });
}
