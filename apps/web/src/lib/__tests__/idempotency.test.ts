import { beforeEach, describe, expect, it } from "vitest";
import {
  hashBody,
  lookupIdempotency,
  saveIdempotency,
  _resetIdempotency,
} from "../idempotency";

beforeEach(() => _resetIdempotency());

describe("idempotency", () => {
  it("first use is new; replay returns the stored response", () => {
    const h = hashBody({ a: 1 });
    expect(lookupIdempotency("k1", "clinic-1", h).kind).toBe("new");
    saveIdempotency("k1", "clinic-1", h, 200, { run_id: "r1" });
    const replay = lookupIdempotency("k1", "clinic-1", h);
    expect(replay).toEqual({ kind: "replay", status: 200, body: { run_id: "r1" } });
  });

  it("same key + different body → conflict", () => {
    saveIdempotency("k2", "clinic-1", hashBody({ a: 1 }), 200, { run_id: "r2" });
    expect(lookupIdempotency("k2", "clinic-1", hashBody({ a: 2 })).kind).toBe("conflict");
  });

  it("keys are scoped per clinic (no cross-tenant probing)", () => {
    saveIdempotency("k3", "clinic-A", hashBody({ a: 1 }), 200, { run_id: "rA" });
    // Same key, different clinic → independent (new).
    expect(lookupIdempotency("k3", "clinic-B", hashBody({ a: 1 })).kind).toBe("new");
  });

  it("expires after the TTL", () => {
    const h = hashBody({ a: 1 });
    const t0 = 1_000_000;
    saveIdempotency("k4", "clinic-1", h, 200, { x: 1 }, t0);
    expect(lookupIdempotency("k4", "clinic-1", h, t0 + 1000).kind).toBe("replay");
    // 25h later → swept.
    expect(lookupIdempotency("k4", "clinic-1", h, t0 + 25 * 60 * 60 * 1000).kind).toBe("new");
  });
});
