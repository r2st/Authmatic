/**
 * Centralized environment access + production safety guards (ticket 0019).
 *
 * `AUTHMATIC_ENV` (development | staging | production) is the source of
 * truth; falls back to NODE_ENV. Demo/fixture shortcuts must never run in
 * production — `assertSafeForProduction()` fails fast at startup if they do.
 *
 * `USE_PYTHON_AGENT` has been removed — the Python agent is now the only
 * execution path (ticket 0025 finalized).
 */

function boolEnv(v: string | undefined): boolean {
  const s = v?.trim().toLowerCase();
  return s === "true" || s === "1" || s === "yes";
}

export const APP_ENV = (
  process.env.AUTHMATIC_ENV ??
  process.env.NODE_ENV ??
  "development"
).toLowerCase();

export const IS_PRODUCTION = APP_ENV === "production";

export const DEMO_FIXTURE_MODE = boolEnv(process.env.DEMO_FIXTURE_MODE);
export const USE_INPROCESS_AGENT = boolEnv(process.env.USE_INPROCESS_AGENT);

export const APP_VERSION =
  process.env.GIT_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA ?? "dev";

/**
 * Refuse to boot in production with demo flags on. Called from
 * instrumentation.register() so a misconfigured prod deploy crashes loudly
 * instead of silently serving scripted/fixture data.
 */
export function assertSafeForProduction(): void {
  if (!IS_PRODUCTION) return;
  const violations: string[] = [];
  if (DEMO_FIXTURE_MODE) violations.push("DEMO_FIXTURE_MODE");
  if (USE_INPROCESS_AGENT) violations.push("USE_INPROCESS_AGENT");
  if (violations.length > 0) {
    throw new Error(
      `Refusing to start: demo flags enabled in production — ${violations.join(", ")}. ` +
        `These bypass the real agent/clinical paths and must be off in prod.`
    );
  }
}
