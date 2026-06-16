import { describe, expect, it } from "vitest";
import { isValidNpi } from "../npi";
import { submitWithRtrvr } from "../sponsors/rtrvr-submit";
import type { PaFormPayload } from "../pa-types";

describe("isValidNpi", () => {
  it("accepts a valid NPI (correct Luhn check digit)", () => {
    expect(isValidNpi("1234567893")).toBe(true);
  });

  it("rejects the fabricated 1234567890 (wrong check digit)", () => {
    expect(isValidNpi("1234567890")).toBe(false);
  });

  it("rejects non-10-digit / non-numeric input", () => {
    expect(isValidNpi("123")).toBe(false);
    expect(isValidNpi("12345678901")).toBe(false);
    expect(isValidNpi("abcdefghij")).toBe(false);
    expect(isValidNpi("")).toBe(false);
    expect(isValidNpi(null)).toBe(false);
  });
});

const PATIENT: PaFormPayload = {
  patient_name: "Maria Martinez",
  dob: "1980-02-14",
  member_id: "HF12345",
  diagnosis: "E11.9",
  medication: "Ozempic",
  dosage: "0.5mg weekly",
  provider_name: "Dr. Emily Chen, MD",
  justification: "Medical necessity.",
};

describe("submitWithRtrvr fail-closed identity (ticket 0031)", () => {
  // With no RTRVR_API_KEY this returns portal_autofill before identity checks,
  // so set a key to exercise the real-path guard.
  it("refuses to submit when no provider is on file", async () => {
    process.env.RTRVR_API_KEY = "test-key";
    const res = await submitWithRtrvr(PATIENT, undefined);
    expect(res.used).toBe(false);
    expect(res.error).toMatch(/prescriber identity missing or NPI invalid/i);
    delete process.env.RTRVR_API_KEY;
  });

  it("refuses to submit when the NPI is invalid", async () => {
    process.env.RTRVR_API_KEY = "test-key";
    const res = await submitWithRtrvr(PATIENT, {
      first_name: "Emily",
      last_name: "Chen",
      npi: "1234567890",
    });
    expect(res.used).toBe(false);
    expect(res.error).toMatch(/NPI invalid/i);
    delete process.env.RTRVR_API_KEY;
  });
});
