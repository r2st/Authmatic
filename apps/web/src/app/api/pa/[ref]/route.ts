import { NextResponse } from "next/server";
import { getSubmission } from "@/lib/submissions";
import { to503 } from "@/lib/persistence-response";

/**
 * PUBLIC by design — this backs the HealthFirst payer-portal confirmation
 * page (`/portal/healthfirst/submission/[ref]`), the simulated *payer's*
 * own status lookup. It is the confirmation-number model: access is gated
 * by knowing the unguessable reference id (ticket 0007), NOT by a clinic
 * session. This is a deliberate deviation from ticket 0005's "every id
 * route is clinic-scoped" rule — the clinic-facing PHI surface (dashboard,
 * runs, batches) IS session-gated; this payer surface is not. Controls for
 * this surface: unguessable refs (0007) + rate limiting (0012). Every read
 * is audited inside getSubmission().
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ ref: string }> }
) {
  const { ref } = await params;
  let submission;
  try {
    submission = await getSubmission(ref);
  } catch (err) {
    return to503(err);
  }

  if (!submission) {
    return NextResponse.json({ error: "Reference ID not found" }, { status: 404 });
  }

  return NextResponse.json(submission);
}
