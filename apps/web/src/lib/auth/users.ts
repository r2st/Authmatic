/**
 * User lookup against InsForge (ticket 0005). Replaces the deleted
 * DEMO_USERS constant. Passwords are stored as scrypt hashes (lib/auth/
 * password.ts); this module never sees plaintext except at verify time.
 *
 * Seed users with scripts/seed-users.mjs. With no InsForge configured,
 * there are no users and every login fails closed (401) — which is the
 * correct posture now that demo auth is gone.
 *
 * Server-only.
 */
import { getInsForgeAdmin, isInsForgeConfigured, IS_PRODUCTION } from "../insforge/admin";
import { isDemoFixtureMode } from "../demo-mode";

export interface UserRecord {
  id: string;
  email: string;
  name: string;
  role: "MA" | "Admin" | "Provider";
  clinic_id: string;
  clinic: string;
  password_hash: string;
}

// Fixture-mode demo user (ticket 0019 / demo path). ONLY reachable when
// DEMO_FIXTURE_MODE is on, which env.ts refuses to allow in production — plus
// the explicit !IS_PRODUCTION belt-and-suspenders here. This restores an
// offline login so the full UI can be demoed without a live InsForge backend;
// it does NOT weaken the real path (InsForge-backed users are used whenever a
// backend is configured). Password: "demo123" (scrypt hash, same format as
// lib/auth/password.ts).
const DEMO_USER: UserRecord = {
  id: "demo-user-0001",
  email: "demo@bayarea-care.com",
  name: "Dr. Emily Chen",
  role: "Provider",
  clinic_id: "demo-clinic-0001",
  clinic: "Bay Area Primary Care",
  password_hash:
    "scrypt$65536$8$1$5nl4ESipBv52u3oWO2BUDw==$9zrD3Naip67It2+CFHbldBHWyrr39jFlkrDTVXR7Y7o=",
};

export async function findUserByEmail(email: string): Promise<UserRecord | null> {
  const normalized = email.toLowerCase().trim();

  // Offline demo: serve the fixture user only in demo mode + non-prod.
  if (isDemoFixtureMode() && !IS_PRODUCTION && normalized === DEMO_USER.email) {
    return DEMO_USER;
  }

  if (!isInsForgeConfigured()) return null;
  try {
    const insforge = getInsForgeAdmin();
    const { data, error } = await insforge.database
      .from("users")
      .select("*")
      .eq("email", normalized)
      .limit(1);
    if (error || !data?.length) return null;
    return data[0] as UserRecord;
  } catch {
    return null;
  }
}
