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
import { getInsForgeAdmin, isInsForgeConfigured } from "../insforge/admin";

export interface UserRecord {
  id: string;
  email: string;
  name: string;
  role: "MA" | "Admin" | "Provider";
  clinic_id: string;
  clinic: string;
  password_hash: string;
}

export async function findUserByEmail(email: string): Promise<UserRecord | null> {
  if (!isInsForgeConfigured()) return null;
  const normalized = email.toLowerCase().trim();
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
