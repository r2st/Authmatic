import { describe, expect, it } from "vitest";
import nextConfig from "../../../next.config";

/**
 * Asserts the security response headers (ticket 0024) are configured for all
 * paths. We test the config's headers() output (the source of truth Next
 * applies to every route incl. /, /dashboard, /portal/*, /api/*).
 */
describe("security headers (ticket 0024)", () => {
  it("applies the required headers to every path", async () => {
    const headers = nextConfig.headers ? await nextConfig.headers() : [];
    const all = headers.flatMap((h) => h.headers);
    const byKey = Object.fromEntries(all.map((h) => [h.key.toLowerCase(), h.value]));

    expect(byKey["strict-transport-security"]).toContain("max-age=63072000");
    // SAMEORIGIN (not DENY): the /run/[id] page frames its own same-origin
    // HealthFirst portal to show live autofill. DENY blanked that iframe in
    // browser testing; cross-origin framing (clickjacking) is still blocked.
    expect(byKey["x-frame-options"]).toBe("SAMEORIGIN");
    expect(byKey["x-content-type-options"]).toBe("nosniff");
    expect(byKey["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(byKey["permissions-policy"]).toMatch(/camera=\(\)/);

    const csp = byKey["content-security-policy-report-only"] ?? byKey["content-security-policy"];
    expect(csp).toContain("default-src 'self'");
    // 'self' to match X-Frame-Options SAMEORIGIN (same-origin portal iframe).
    expect(csp).toContain("frame-ancestors 'self'");
    expect(csp).toContain("report-uri /api/csp-report");
  });

  it("matches all paths via the source pattern", async () => {
    const headers = nextConfig.headers ? await nextConfig.headers() : [];
    expect(headers.some((h) => h.source === "/:path*")).toBe(true);
  });
});
