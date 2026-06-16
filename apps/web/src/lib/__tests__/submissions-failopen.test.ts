import { afterEach, describe, expect, it } from "vitest";
import { createSubmission, listSubmissions, PersistenceError } from "../submissions";
import type { PaFormPayload } from "../pa-types";

const PAYLOAD: PaFormPayload = {
  patient_name: "Maria Martinez",
  dob: "1980-02-14",
  member_id: "HF12345",
  diagnosis: "E11.9",
  medication: "Ozempic",
  dosage: "0.5mg weekly",
  provider_name: "Dr. Emily Chen, MD",
  justification: "Medical necessity.",
};

afterEach(() => {
  delete process.env.DEMO_FIXTURE_MODE;
  delete process.env.INSFORGE_PROJECT_URL;
  delete process.env.INSFORGE_API_KEY;
});

describe("submissions fail-loud (ticket 0016)", () => {
  it("throws PersistenceError when InsForge is unconfigured and not in fixture mode", async () => {
    // No INSFORGE_* env, no DEMO_FIXTURE_MODE → must NOT silently use memory.
    await expect(createSubmission(PAYLOAD)).rejects.toBeInstanceOf(PersistenceError);
  });

  it("listSubmissions also throws (no silent empty/in-memory result)", async () => {
    await expect(listSubmissions(10)).rejects.toBeInstanceOf(PersistenceError);
  });

  it("fixture mode is the only legitimate offline path", async () => {
    process.env.DEMO_FIXTURE_MODE = "true";
    const sub = await createSubmission(PAYLOAD);
    expect(sub.reference_id).toMatch(/^PA-/);
    // And it is readable back from the fixture store.
    const list = await listSubmissions(10);
    expect(list.some((s) => s.reference_id === sub.reference_id)).toBe(true);
  });
});
