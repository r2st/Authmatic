import { afterAll, describe, expect, it } from "vitest";
import { scopedQuery, adminQuery, closePools } from "../db";

/**
 * Proves RLS is enforced AT RUNTIME through the tenant-scoped client (ticket
 * 0034): a clinic-B-scoped connection cannot read a clinic-A row, even with no
 * `WHERE clinic_id` filter. Requires the local dev Postgres reachable as the
 * non-superuser `authmatic_app` role (migrations 0007/0010/0011 applied +
 * `ALTER ROLE authmatic_app LOGIN`). Skips otherwise.
 *
 * Run: APP_DATABASE_URL=postgres://authmatic_app:app_local_pw@localhost:55432/authmatic \
 *      ADMIN_DATABASE_URL=postgres://authmatic:authmatic@localhost:55432/authmatic \
 *      pnpm --filter authmatic-web exec vitest run src/lib/__tests__/db-rls.test.ts
 */
const A = "11111111-1111-1111-1111-111111111111";
const B = "22222222-2222-2222-2222-222222222222";

afterAll(async () => {
  await closePools();
});

describe("runtime RLS via scoped client (ticket 0034)", () => {
  it("clinic B cannot read clinic A's patient; clinic A can", async () => {
    if (!process.env.APP_DATABASE_URL) {
      // Without the app-role connection string we can't exercise RLS.
      return;
    }
    let ok = true;
    try {
      await adminQuery("SELECT 1");
    } catch {
      ok = false; // no DB reachable
    }
    if (!ok) return;

    const member = `RLS-DB-${Date.now()}`;
    // Seed via the privileged connection (bypasses RLS): two clinics + a
    // patient owned by clinic A.
    await adminQuery("INSERT INTO clinics (id,name) VALUES ($1,'A') ON CONFLICT DO NOTHING", [A]);
    await adminQuery("INSERT INTO clinics (id,name) VALUES ($1,'B') ON CONFLICT DO NOTHING", [B]);
    await adminQuery(
      "INSERT INTO patients (full_name,dob,plan_id,member_id,clinic_id) VALUES ('RLS DB Test','1990-01-01','P',$1,$2)",
      [member, A]
    );

    try {
      // No WHERE clinic_id — RLS must still scope by the SET app.clinic_id.
      const asA = await scopedQuery(A, "SELECT member_id FROM patients WHERE member_id=$1", [member]);
      const asB = await scopedQuery(B, "SELECT member_id FROM patients WHERE member_id=$1", [member]);
      expect(asA.length).toBe(1); // owner sees it
      expect(asB.length).toBe(0); // other tenant is blocked by RLS
    } finally {
      await adminQuery("DELETE FROM patients WHERE member_id=$1", [member]);
    }
  });
});
