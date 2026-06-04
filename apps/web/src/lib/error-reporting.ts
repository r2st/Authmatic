/**
 * Error-reporting chokepoint (ticket 0011). One function to capture an
 * exception with redacted context. If Sentry is configured (`SENTRY_DSN` set
 * and `@sentry/nextjs` installed) it forwards there; otherwise it falls back
 * to the structured logger so nothing is ever swallowed.
 *
 * Keeping the SDK behind a dynamic import means the app builds and runs with
 * or without Sentry installed — wiring the live DSN is an ACTION REQUIRED
 * step (see ADR 0009), not a hard build dependency.
 *
 * PHI is redacted via the logger / redactPhi before anything leaves.
 * Server-only.
 */
import { log } from "./logging";
import { redactPhi } from "./phi";

type Context = Record<string, unknown>;

let sentryLoaded: boolean | null = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let sentry: any = null;

async function ensureSentry(): Promise<boolean> {
  if (sentryLoaded !== null) return sentryLoaded;
  if (!process.env.SENTRY_DSN) {
    sentryLoaded = false;
    return false;
  }
  try {
    // Computed specifier so the optional dependency isn't resolved at
    // type-check / build time when it isn't installed.
    const mod = "@sentry/nextjs";
    sentry = await import(/* webpackIgnore: true */ mod).catch(() => null);
    sentryLoaded = Boolean(sentry);
  } catch {
    sentryLoaded = false;
  }
  return sentryLoaded;
}

export async function captureError(err: unknown, context?: Context): Promise<void> {
  const safe = context ? redactPhi(context) : undefined;
  log.error("error.captured", {
    ...safe,
    error: err instanceof Error ? err.message : String(err),
  });
  if (await ensureSentry()) {
    sentry.captureException(err, { extra: safe });
  }
}
