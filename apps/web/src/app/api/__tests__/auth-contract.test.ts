import { describe, expect, it, vi } from "vitest";

// Simulate a request with NO session cookie. getServerSession() reads the
// cookie via next/headers; mock it to return an empty store.
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => undefined }),
}));

describe("API auth contract — clinic routes reject unauthenticated (ticket 0005)", () => {
  it("GET /api/dashboard → 401 without a session", async () => {
    const { GET } = await import("../dashboard/route");
    const res = await GET();
    expect(res.status).toBe(401);
  });

  it("GET /api/run → 401 without a session", async () => {
    const { GET } = await import("../run/route");
    const res = await GET();
    expect(res.status).toBe(401);
  });

  it("GET /api/security-log → 401 without a session", async () => {
    const { GET } = await import("../security-log/route");
    const res = await GET();
    expect(res.status).toBe(401);
  });

  it("GET /api/run/[id] → 401 without a session", async () => {
    const { GET } = await import("../run/[id]/route");
    const res = await GET(new Request("http://t/api/run/abc"), {
      params: Promise.resolve({ id: "abc" }),
    });
    expect(res.status).toBe(401);
  });
});
