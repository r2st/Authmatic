#!/usr/bin/env node
/**
 * Seed clinic users into InsForge with scrypt-hashed passwords (ticket 0005).
 *
 * Usage:
 *   SEED_USER_PASSWORD='choose-a-strong-pw' node scripts/seed-users.mjs
 *
 * If SEED_USER_PASSWORD is unset, a random password is generated and printed
 * once. Passwords are NEVER written to source — only their scrypt hashes
 * reach the DB. Re-runnable: upserts by email.
 *
 * Requires INSFORGE_PROJECT_URL + INSFORGE_API_KEY in the environment.
 */
import { scrypt as _scrypt, randomBytes } from "node:crypto";
import { promisify } from "node:util";
import { createAdminClient } from "@insforge/sdk";

const scrypt = promisify(_scrypt);
const N = 1 << 16, R = 8, P = 1, KEYLEN = 32;

async function hashPassword(password) {
  const salt = randomBytes(16);
  const derived = await scrypt(password, salt, KEYLEN, { N, r: R, p: P, maxmem: 256 * 1024 * 1024 });
  return `scrypt$${N}$${R}$${P}$${salt.toString("base64")}$${derived.toString("base64")}`;
}

const SEED = [
  { email: "emily.chen@bayarea-care.com", name: "Emily Chen, MD", role: "Provider", clinic: "Bay Area Primary Care" },
  { email: "ma@bayarea-care.com", name: "Sarah Kim", role: "MA", clinic: "Bay Area Primary Care" },
];

async function main() {
  const baseUrl = process.env.INSFORGE_PROJECT_URL?.trim();
  const apiKey = process.env.INSFORGE_API_KEY?.trim();
  if (!baseUrl || !apiKey) {
    console.error("Missing INSFORGE_PROJECT_URL / INSFORGE_API_KEY");
    process.exit(1);
  }

  const password = process.env.SEED_USER_PASSWORD || randomBytes(12).toString("base64url");
  if (!process.env.SEED_USER_PASSWORD) {
    console.log(`Generated demo password (save it now, shown once): ${password}`);
  }
  const password_hash = await hashPassword(password);

  const insforge = createAdminClient({ baseUrl, apiKey });
  for (const u of SEED) {
    const row = { ...u, email: u.email.toLowerCase(), password_hash };
    // delete-then-insert keeps the script idempotent without relying on upsert semantics
    await insforge.database.from("users").delete().eq("email", row.email);
    const { error } = await insforge.database.from("users").insert([row]);
    if (error) {
      console.error(`Failed to seed ${row.email}: ${error.message}`);
      process.exit(1);
    }
    console.log(`Seeded ${row.email} (${row.role}, ${row.clinic})`);
  }
  console.log("Done. All seeded users share the password above.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
