import { NextRequest, NextResponse } from "next/server";
import { auditLog } from "@/lib/audit";
import { verifyPassword } from "@/lib/auth/password";
import { sessionCookieOptions, signSession, SESSION_COOKIE } from "@/lib/auth/session";
import { findUserByEmail } from "@/lib/auth/users";

/**
 * POST /api/auth/login — verify credentials, issue a signed session cookie.
 * Brute-force rate limiting (5 / IP / 15min) is applied by middleware (0012).
 */
export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as { email?: string; password?: string };
  const email = (body.email ?? "").toLowerCase().trim();
  const password = body.password ?? "";

  if (!email || !password) {
    return NextResponse.json({ error: "Email and password required" }, { status: 400 });
  }

  const user = await findUserByEmail(email);
  // Always run a verify to keep timing roughly constant whether or not the
  // user exists (avoids user-enumeration via response time).
  const ok = user ? await verifyPassword(password, user.password_hash) : await verifyPassword(password, DUMMY_HASH);

  if (!user || !ok) {
    void auditLog({ action: "login", resource: "session", allowed: false, detail: { email_domain: email.split("@")[1] ?? null } });
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const token = signSession({
    sub: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    clinic_id: user.clinic_id ?? user.clinic, // clinic_id arrives with 0006; clinic name is the tenant key until then
    clinic: user.clinic,
  });

  void auditLog({ action: "login", resource: "session", actor_id: user.id, actor_clinic: user.clinic_id ?? user.clinic, allowed: true });

  const res = NextResponse.json({
    user: { email: user.email, name: user.name, role: user.role, clinic: user.clinic },
  });
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  return res;
}

// A fixed scrypt hash of a random string, used only to equalize timing for
// unknown users. Not a real credential.
const DUMMY_HASH =
  "scrypt$65536$8$1$AAAAAAAAAAAAAAAAAAAAAA==$Ld8nQ0m0n0pQrStUvWxYz0123456789abcdefghijkl=";
