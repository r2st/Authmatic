/**
 * PHI redaction helpers. Pure, dependency-free.
 *
 * Enforces the logging rules in ADR 0008 (docs/decisions/0008-phi-handling-policy.md):
 * no raw PHI field may be logged or sent to a third party. Use `redact()`
 * for a single value, `redactPhi()` to scrub an object before it reaches a
 * logger, an LLM prompt, or an analytics sink.
 *
 * The structured logger (apps/web/src/lib/logging.ts, ticket 0011) wraps
 * these so every log line is redacted by construction.
 */

/** Field names that carry PHI in our schema (see ADR 0008 field table). */
export const PHI_KEYS = new Set([
  "patient_name",
  "patient_first_name",
  "patient_last_name",
  "full_name",
  "dob",
  "member_id",
  "primary_patient_id",
  "patient_ssn",
  "ssn",
  "diagnosis",
  "diagnosis_code",
  "icd10",
  "justification",
  "rationale",
  "raw_text",
]);

/** Mask all but the last `keep` characters: "UHC8842910" -> "******2910". */
export function maskTail(value: string, keep = 4): string {
  if (value.length <= keep) return "*".repeat(value.length);
  return "*".repeat(value.length - keep) + value.slice(-keep);
}

/** Reduce a name to initials: "Maria Martinez" -> "M.M." */
export function initials(value: string): string {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  return parts.map((p) => `${p[0]!.toUpperCase()}.`).join("");
}

/**
 * Redact one PHI value according to its field. Identifiers keep a short
 * suffix for correlation; free text and dates are fully masked.
 */
export function redact(key: string, value: unknown): string {
  if (value == null) return "";
  const s = String(value);
  switch (key) {
    case "patient_name":
    case "patient_first_name":
    case "patient_last_name":
    case "full_name":
      return initials(s);
    case "member_id":
    case "primary_patient_id":
      return maskTail(s, 4);
    case "patient_ssn":
    case "ssn":
      return "***-**-****";
    case "dob":
      return "****-**-**";
    default:
      // Free-text PHI (diagnosis, justification, rationale, raw_text): keep
      // only a length signal, never the content.
      return `[redacted ${s.length} chars]`;
  }
}

/**
 * Return a shallow copy of `obj` with every PHI key redacted. Non-PHI keys
 * pass through unchanged. Use before logging or before building an LLM
 * prompt from a record that may contain PHI.
 */
export function redactPhi<T extends Record<string, unknown>>(obj: T): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    out[k] = PHI_KEYS.has(k) ? redact(k, v) : v;
  }
  return out;
}
