/**
 * Structured logger for the web service (ticket 0011).
 *
 * JSON to stdout via pino, level from `LOG_LEVEL` (default "info"). Every
 * context object is run through `redactPhi` (ADR 0008) so PHI can never land
 * in a log line by construction — pass records freely, the logger masks
 * member_id / name / dob / free-text before they leave the process.
 *
 * Always include correlation fields where available: request_id, clinic_id,
 * run_id. Use `log.child({ request_id, clinic_id })` per request.
 *
 * Server-only.
 */
import pino from "pino";
import { redactPhi } from "./phi";

const base = pino({
  level: process.env.LOG_LEVEL ?? "info",
  base: { service: "authmatic-web" },
  // Redact known PHI key paths defensively even if a caller forgets redactPhi.
  redact: {
    paths: ["member_id", "patient_name", "dob", "patient_ssn", "ssn", "justification", "rationale", "*.member_id", "*.patient_name", "*.dob"],
    censor: "[redacted]",
  },
  formatters: {
    level: (label) => ({ level: label }),
  },
});

type Context = Record<string, unknown>;

function emit(level: "info" | "warn" | "error", event: string, context?: Context): void {
  // Redact PHI keys in the supplied context before logging.
  base[level](context ? redactPhi(context) : {}, event);
}

export const log = {
  info: (event: string, context?: Context) => emit("info", event, context),
  warn: (event: string, context?: Context) => emit("warn", event, context),
  error: (event: string, context?: Context) => emit("error", event, context),
  /** Per-request child logger carrying correlation ids. */
  child: (bindings: Context) => base.child(redactPhi(bindings)),
};
