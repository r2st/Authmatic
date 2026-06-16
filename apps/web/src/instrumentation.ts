/**
 * Next.js instrumentation hook — runs once at server startup.
 * Used here for the production safety guard (ticket 0019). Error reporting
 * (Sentry/Datadog) registration will also live here per ticket 0011.
 */
import { assertSafeForProduction } from "@/lib/env";

export async function register() {
  assertSafeForProduction();
}
