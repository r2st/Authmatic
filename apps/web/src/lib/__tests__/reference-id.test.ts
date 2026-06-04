import { describe, expect, it } from "vitest";
import { newReferenceId, isValidReferenceId, REFERENCE_ID_RE } from "../reference-id";

describe("reference-id", () => {
  it("generates the PA-<16 hex> format", () => {
    const id = newReferenceId();
    expect(id).toMatch(/^PA-[0-9A-F]{16}$/);
    expect(isValidReferenceId(id)).toBe(true);
  });

  it("is non-sequential / unguessable (distinct across calls)", () => {
    const ids = new Set(Array.from({ length: 1000 }, () => newReferenceId()));
    expect(ids.size).toBe(1000); // no collisions in 1k draws
  });

  it("rejects the old sequential format", () => {
    expect(isValidReferenceId("PA-2026-00451")).toBe(false);
  });

  it("REFERENCE_ID_RE extracts an id embedded in text", () => {
    const id = newReferenceId();
    const m = `submitted as ${id} ok`.match(REFERENCE_ID_RE);
    expect(m?.[0]).toBe(id);
  });
});
