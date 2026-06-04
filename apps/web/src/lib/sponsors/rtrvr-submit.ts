import type { PaFormPayload } from "../pa-types";
import { isValidNpi } from "../npi";
import { REFERENCE_ID_RE } from "../reference-id";

/**
 * Verified prescriber identity for a real submission (ticket 0031). Sourced
 * from a `providers` record, NEVER a literal. Required before any real
 * payer submit — see `submitWithRtrvr`.
 */
export type Prescriber = {
  first_name: string;
  last_name: string;
  npi: string;
};

export type RtrvrResult = {
  used: boolean;
  mode: "rtrvr_api" | "portal_autofill";
  http_status?: number;
  reference_id?: string;
  response?: unknown;
  error?: string;
};

/** Split a "Maria Martinez, MD" style name into parts; empty strings if absent. */
function splitPatientName(full: string): { first: string; last: string } {
  const parts = (full ?? "").trim().split(/\s+/).filter(Boolean);
  return { first: parts[0] ?? "", last: parts.slice(1).join(" ") };
}

function portalUrl(): string {
  if (process.env.PORTAL_URL?.trim()) return process.env.PORTAL_URL.trim();
  const base =
    process.env.WEB_URL?.trim() ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");
  return `${base.replace(/\/$/, "")}/portal/healthfirst/prior-auth`;
}

function parseReferenceId(text: string): string | undefined {
  const m = text.match(REFERENCE_ID_RE);
  return m?.[0]?.toUpperCase();
}

/**
 * Call the Rtrvr Agent API to fill + submit the HealthFirst portal.
 *
 * `prescriber` MUST be a verified provider record with a valid NPI (ticket
 * 0031). If it is missing or the NPI fails validation we REFUSE to submit
 * rather than fabricate identity — a wrong/fake NPI on a real payer
 * submission is at best an instant denial, at worst fraud. Patient identity
 * likewise comes only from `fields`; no literal fallbacks.
 */
export async function submitWithRtrvr(
  fields: PaFormPayload,
  prescriber?: Prescriber
): Promise<RtrvrResult> {
  const apiKey = process.env.RTRVR_API_KEY?.trim();
  if (!apiKey) {
    return { used: false, mode: "portal_autofill" };
  }

  // Fail closed on missing/invalid identity — never substitute a literal.
  if (!prescriber || !isValidNpi(prescriber.npi)) {
    return {
      used: false,
      mode: "rtrvr_api",
      error:
        "Refusing to submit: prescriber identity missing or NPI invalid. " +
        "Provider must be on file with a valid 10-digit NPI (ticket 0031).",
    };
  }
  const patient = splitPatientName(fields.patient_name);
  if (!patient.first || !patient.last || !fields.member_id || !fields.dob) {
    return {
      used: false,
      mode: "rtrvr_api",
      error: "Refusing to submit: incomplete patient identity (name/DOB/member id).",
    };
  }

  const url = portalUrl();
  const input = [
    "Fill the Prescription Drug Prior Authorization form (Page 1) and submit.",
    `Open ${url}`,
    "Patient section:",
    `#patient_first_name: ${patient.first}`,
    `#patient_last_name: ${patient.last}`,
    `#patient_dob: ${fields.dob}`,
    `#primary_patient_id: ${fields.member_id}`,
    `#primary_insurance_name: HealthFirst PPO`,
    "Prescriber section:",
    `#prescriber_first_name: ${prescriber.first_name}`,
    `#prescriber_last_name: ${prescriber.last_name}`,
    `#prescriber_npi: ${prescriber.npi}`,
    "Medication section:",
    `#medication_name: ${fields.medication}`,
    `#medication_dose + #medication_frequency: ${fields.dosage}`,
    `#diagnosis_primary: ${fields.diagnosis}`,
    `#clinical_justification: ${fields.justification}`,
    "Check #therapy_new and #medication_route_injection if applicable.",
    "Click #submit-prior-auth when complete.",
    "Return reference_id from /portal/healthfirst/submission/PA-... URL.",
  ].join("\n");

  try {
    const res = await fetch("https://api.rtrvr.ai/agent", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        input,
        urls: [url],
        response: { verbosity: "final" },
      }),
      signal: AbortSignal.timeout(12000),
    });

    const raw = await res.text();
    let parsed: unknown = raw;
    try {
      parsed = JSON.parse(raw);
    } catch {
      /* keep text */
    }

    const text = typeof parsed === "string" ? parsed : JSON.stringify(parsed);
    const reference_id = parseReferenceId(text);

    if (!res.ok) {
      return {
        used: true,
        mode: "rtrvr_api",
        http_status: res.status,
        error: text.slice(0, 300),
        response: parsed,
      };
    }

    return {
      used: true,
      mode: "rtrvr_api",
      http_status: res.status,
      reference_id,
      response: parsed,
    };
  } catch (err) {
    return {
      used: true,
      mode: "rtrvr_api",
      error: err instanceof Error ? err.message : "Rtrvr request failed",
    };
  }
}

export function isRtrvrConfigured(): boolean {
  return Boolean(process.env.RTRVR_API_KEY?.trim());
}
