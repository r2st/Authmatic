/**
 * Client-side auth helpers (ticket 0005). The session lives in an httpOnly
 * cookie validated server-side — it is NOT readable from JS. These helpers
 * just talk to the auth API. No passwords, no DEMO_USERS, no localStorage.
 */

export type ClinicUser = {
  email: string;
  name: string;
  role: "MA" | "Admin" | "Provider";
  clinic: string;
};

/** Fetch the current user from the signed session cookie. Null if signed out. */
export async function fetchSession(): Promise<ClinicUser | null> {
  try {
    const res = await fetch("/api/auth/session", { cache: "no-store" });
    if (!res.ok) return null;
    const data = (await res.json()) as { user: ClinicUser | null };
    return data.user;
  } catch {
    return null;
  }
}

/** Exchange credentials for a session cookie. Returns the user or null. */
export async function loginRequest(email: string, password: string): Promise<ClinicUser | null> {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { user: ClinicUser };
    return data.user;
  } catch {
    return null;
  }
}

/** Clear the session cookie. */
export async function logoutRequest(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {
    /* best effort */
  }
}
