import { beforeEach, describe, expect, it } from "vitest";
import { rulesFor, slidingWindow, _resetRateLimits, RATE_LIMITS } from "../rate-limits";

beforeEach(() => _resetRateLimits());

describe("rulesFor", () => {
  it("matches /api/run POST", () => {
    expect(rulesFor("POST", "/api/run")?.key).toBe("POST /api/run");
  });
  it("matches /api/pa/[ref] GET to the /api/pa lookup rule", () => {
    expect(rulesFor("GET", "/api/pa/PA-ABC")?.key).toBe("GET /api/pa");
  });
  it("prefers the longer prefix (/api/pa/submit over /api/pa)", () => {
    expect(rulesFor("POST", "/api/pa/submit")?.key).toBe("POST /api/pa/submit");
  });
  it("returns null for unlimited routes", () => {
    expect(rulesFor("GET", "/api/dashboard")).toBeNull();
  });
});

describe("slidingWindow", () => {
  it("allows up to the limit then blocks (11th of 10/min → 429)", () => {
    const rule = RATE_LIMITS["POST /api/run"][0]; // 10 / minute
    const now = 1_000_000;
    for (let i = 0; i < 10; i++) {
      expect(slidingWindow("k", rule, now).allowed).toBe(true);
    }
    const blocked = slidingWindow("k", rule, now);
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.retryAfterSec).toBeGreaterThan(0);
  });

  it("frees up after the window slides", () => {
    const rule = { limit: 2, windowMs: 1000, by: "ip" as const };
    expect(slidingWindow("k2", rule, 0).allowed).toBe(true);
    expect(slidingWindow("k2", rule, 100).allowed).toBe(true);
    expect(slidingWindow("k2", rule, 200).allowed).toBe(false);
    // 1.1s later the first two hits have aged out.
    expect(slidingWindow("k2", rule, 1200).allowed).toBe(true);
  });

  it("buckets are independent", () => {
    const rule = { limit: 1, windowMs: 1000, by: "ip" as const };
    expect(slidingWindow("a", rule, 0).allowed).toBe(true);
    expect(slidingWindow("b", rule, 0).allowed).toBe(true);
    expect(slidingWindow("a", rule, 0).allowed).toBe(false);
  });
});
