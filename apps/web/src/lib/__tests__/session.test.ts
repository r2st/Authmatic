import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { signSession, verifySession } from "../auth/session";

const BASE = {
  sub: "u1",
  email: "ma@clinic.test",
  name: "MA",
  role: "MA" as const,
  clinic_id: "clinic-1",
  clinic: "Clinic One",
};

describe("session sign/verify (ticket 0005)", () => {
  beforeEach(() => {
    process.env.SESSION_SECRET = "test-secret-at-least-16-chars-long";
  });
  afterEach(() => {
    delete process.env.SESSION_SECRET;
  });

  it("round-trips a valid session", () => {
    const token = signSession(BASE);
    const out = verifySession(token);
    expect(out?.email).toBe(BASE.email);
    expect(out?.clinic_id).toBe("clinic-1");
  });

  it("rejects a tampered payload", () => {
    const token = signSession(BASE);
    const sig = token.split(".")[1];
    const forged = Buffer.from(JSON.stringify({ ...BASE, clinic_id: "clinic-2", exp: 9999999999 }))
      .toString("base64url");
    expect(verifySession(`${forged}.${sig}`)).toBeNull();
  });

  it("rejects an expired session", () => {
    const token = signSession({ ...BASE, exp: Math.floor(Date.now() / 1000) - 10 });
    expect(verifySession(token)).toBeNull();
  });

  it("rejects garbage / empty", () => {
    expect(verifySession(undefined)).toBeNull();
    expect(verifySession("not-a-token")).toBeNull();
  });
});
