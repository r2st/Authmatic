/**
 * Server-side authz helpers used by every API route (ticket 0005).
 *
 *   const session = await getServerSession();
 *   if (!session) return unauthorized();
 *
 * and for id-scoped resources:
 *
 *   if (!ownsResource(session, run.clinic_id)) return notFoundLeakSafe();
 *
 * Cross-tenant access returns 404 (not 403) so resource existence is never
 * leaked, and is recorded as an `access_denied` audit event.
 *
 * Server-only.
 */
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { auditLog } from "../audit";
import { SESSION_COOKIE, verifySession, type ClinicSession } from "./session";

export type { ClinicSession };

/** Read + verify the session cookie. Returns null when unauthenticated. */
export async function getServerSession(): Promise<ClinicSession | null> {
  const store = await cookies();
  return verifySession(store.get(SESSION_COOKIE)?.value);
}

export function unauthorized(): NextResponse {
  return NextResponse.json({ error: "Authentication required" }, { status: 401 });
}

/** Existence-leak-safe denial for cross-tenant / missing resources. */
export function notFoundLeakSafe(): NextResponse {
  return NextResponse.json({ error: "Not found" }, { status: 404 });
}

/** True if the session's clinic owns a resource tagged with `clinicId`. */
export function ownsResource(session: ClinicSession, clinicId: string | undefined | null): boolean {
  if (!clinicId) return false;
  return session.clinic_id === clinicId;
}

/**
 * Guard an id-scoped resource. If the caller's clinic does not own it,
 * writes an access_denied audit row and returns a 404 response; otherwise
 * returns null (caller proceeds).
 */
export async function denyIfNotOwner(
  session: ClinicSession,
  resource: string,
  resourceId: string,
  ownerClinicId: string | undefined | null
): Promise<NextResponse | null> {
  if (ownsResource(session, ownerClinicId)) return null;
  void auditLog({
    action: "access_denied",
    resource,
    resource_id: resourceId,
    actor_id: session.sub,
    actor_clinic: session.clinic_id,
    allowed: false,
  });
  return notFoundLeakSafe();
}
