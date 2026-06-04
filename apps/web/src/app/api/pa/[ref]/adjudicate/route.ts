import { NextRequest, NextResponse } from "next/server";
import { adjudicateReference } from "@/lib/adjudication";
import { getSubmission } from "@/lib/submissions";

/**
 * Simulates HealthFirst medical review — NOT auto-called on submit.
 * Agent backend calls this after form submission to run payer adjudication.
 *
 * PUBLIC by design — this is the simulated *payer's* review action, keyed
 * by the unguessable reference id (ticket 0007), not a clinic session. The
 * field-level allowlist for what this may mutate is tightened in ticket
 * 0018 (it must not accept an arbitrary patch). Rate-limited via 0012.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ ref: string }> }
) {
  const { ref } = await params;
  const submission = await getSubmission(ref);

  if (!submission) {
    return NextResponse.json({ error: "Reference ID not found" }, { status: 404 });
  }

  if (submission.status === "approved" || submission.status === "denied") {
    return NextResponse.json({
      reference_id: ref,
      status: submission.status,
      decision_notes: submission.decision_notes,
      denial_reason: submission.denial_reason,
      reviewer_id: submission.reviewer_id,
      message: "Decision already recorded",
    });
  }

  const body = await request.json().catch(() => ({}));
  const reviewDelayMs =
    typeof body.review_delay_ms === "number" ? body.review_delay_ms : 8000;

  const result = await adjudicateReference(ref, reviewDelayMs);

  if (!result) {
    return NextResponse.json({ error: "Adjudication failed" }, { status: 500 });
  }

  return NextResponse.json({
    ...result,
    message:
      result.status === "approved"
        ? "Prior authorization approved by HealthFirst medical review."
        : "Prior authorization denied by HealthFirst medical review.",
  });
}
