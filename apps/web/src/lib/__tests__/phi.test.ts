import { describe, expect, it } from "vitest";
import { redact, redactPhi, maskTail, initials } from "../phi";

describe("phi redaction", () => {
  it("masks member_id keeping last 4", () => {
    expect(redact("member_id", "UHC8842910")).toBe("******2910");
  });

  it("reduces names to initials", () => {
    expect(redact("patient_name", "Maria Martinez")).toBe("M.M.");
    expect(initials("emily chen")).toBe("E.C.");
  });

  it("fully masks dob and ssn", () => {
    expect(redact("dob", "1980-02-14")).toBe("****-**-**");
    expect(redact("patient_ssn", "123-45-6789")).toBe("***-**-****");
  });

  it("masks free-text PHI to a length signal only", () => {
    expect(redact("justification", "patient needs drug")).toMatch(/^\[redacted \d+ chars\]$/);
  });

  it("redactPhi scrubs PHI keys but keeps non-PHI", () => {
    const out = redactPhi({ member_id: "UHC8842910", drug_name: "Ozempic", status: "approved" });
    expect(out.member_id).toBe("******2910");
    expect(out.drug_name).toBe("Ozempic");
    expect(out.status).toBe("approved");
  });

  it("maskTail handles short strings", () => {
    expect(maskTail("ab", 4)).toBe("**");
  });
});
