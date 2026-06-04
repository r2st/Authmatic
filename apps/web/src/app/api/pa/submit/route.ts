import { NextRequest, NextResponse } from "next/server";
import { portalValuesToPayload } from "@/lib/portal-form-data";
import type { PaFormPayload } from "@/lib/pa-types";
import { createSubmission } from "@/lib/submissions";

function formDataToPayload(form: FormData): PaFormPayload {
  const raw = Object.fromEntries(form.entries()) as Record<string, string>;
  if (raw.patient_first_name || raw.primary_patient_id) {
    return portalValuesToPayload(raw);
  }
  return {
    patient_name: String(form.get("patient_name") ?? ""),
    dob: String(form.get("dob") ?? ""),
    member_id: String(form.get("member_id") ?? ""),
    diagnosis: String(form.get("diagnosis") ?? ""),
    medication: String(form.get("medication") ?? ""),
    dosage: String(form.get("dosage") ?? ""),
    provider_name: String(form.get("provider_name") ?? ""),
    justification: String(form.get("justification") ?? ""),
  };
}

/**
 * PUBLIC by design — payer-portal intake. This is the simulated HealthFirst
 * form that a clinic (or the Rtrvr agent, headless) fills and submits. The
 * Rtrvr browser session carries no clinic cookie, so this route cannot
 * require an Authmatic session. Submissions land with no clinic owner
 * (clinic_id null) — the payer intake doesn't know which Authmatic tenant
 * sent them. Controls: rate limiting (0012). See ticket 0005 Log for the
 * payer-vs-clinic boundary rationale.
 */
export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") ?? "";
  let payload: PaFormPayload;

  if (contentType.includes("application/json")) {
    const body = (await request.json()) as Record<string, string>;
    payload =
      body.patient_first_name || body.primary_patient_id
        ? portalValuesToPayload(body)
        : (body as unknown as PaFormPayload);
  } else {
    const form = await request.formData();
    payload = formDataToPayload(form);
  }

  const submission = await createSubmission(payload);
  const status_path = `/portal/healthfirst/submission/${submission.reference_id}`;
  const base = request.nextUrl.origin;

  const accept = request.headers.get("accept") ?? "";
  if (contentType.includes("application/json") || accept.includes("application/json")) {
    return NextResponse.json({
      reference_id: submission.reference_id,
      status: submission.status,
      status_url: status_path,
      message:
        "Prior authorization request received. Status: Pending Review. Medical review typically completes within 24–72 hours.",
    });
  }

  return NextResponse.redirect(`${base}${status_path}`, 303);
}
