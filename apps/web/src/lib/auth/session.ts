/**
 * Signed session tokens. Stateless, HMAC-SHA256 signed (no external dep).
 *
 * Token = base64url(JSON payload) + "." + base64url(HMAC). The payload holds
 * the minimum-necessary identity (no PHI). Verified server-side on every
 * request via lib/auth/server.ts. Stored in an httpOnly, secure, sameSite=lax
 * cookie so it is never readable from client JS (defeats XSS token theft).
 *
 * Server-only.
 */
import { createHmac, timingSafeEqual } from "crypto";

export const SESSION_COOKIE = "authmatic_session";
export const SESSION_TTL_SECONDS = 60 * 60 * 8; // 8h

export interface ClinicSession {
  sub: string; // user id
  email: string;
  name: string;
  role: "MA" | "Admin" | "Provider";
  clinic_id: string; // tenant key — used for ownership checks
  clinic: string; // display name
  exp: number; // unix seconds
}

function secret(): string {
  const s = process.env.SESSION_SECRET?.trim();
  if (s && s.length >= 16) return s;
  if (process.env.NODE_ENV === "production") {
    throw new Error("SESSION_SECRET missing or too short (>=16 chars required) in production");
  }
  // Dev-only stable fallback so `pnpm dev` works without setup. NEVER used in prod.
  return "dev-insecure-session-secret-do-not-use-in-prod";
}

function b64url(buf: Buffer | string): string {
  return Buffer.from(buf).toString("base64url");
}

export function signSession(payload: Omit<ClinicSession, "exp"> & { exp?: number }): string {
  const full: ClinicSession = {
    ...payload,
    exp: payload.exp ?? Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS,
  };
  const body = b64url(JSON.stringify(full));
  const sig = createHmac("sha256", secret()).update(body).digest("base64url");
  return `${body}.${sig}`;
}

export function verifySession(token: string | undefined | null): ClinicSession | null {
  if (!token) return null;
  const dot = token.lastIndexOf(".");
  if (dot < 1) return null;
  const body = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = createHmac("sha256", secret()).update(body).digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const parsed = JSON.parse(Buffer.from(body, "base64url").toString()) as ClinicSession;
    if (typeof parsed.exp !== "number" || parsed.exp < Math.floor(Date.now() / 1000)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}
