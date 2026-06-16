import { NextRequest, NextResponse } from "next/server";
import { rulesFor, slidingWindow } from "@/lib/rate-limits";

// Inlined (not imported from lib/auth/session) so the edge middleware bundle
// doesn't pull in node:crypto. Must match SESSION_COOKIE there.
const SESSION_COOKIE = "authmatic_session";

/**
 * Edge middleware: request-id/tracing (ticket 0021) + rate limiting (0012).
 *
 * Every request gets an `X-Request-ID` (accepted from the caller or minted);
 * it's threaded onto the request (so route handlers + the agent proxy forward
 * it) and echoed on the response — the seam distributed tracing builds on.
 *
 * Rate limiting: keyed per-session (signed cookie value as an opaque bucket)
 * or per-IP; a 429 never reveals other clinics' activity. Counters are
 * in-process; see lib/rate-limits.ts for the Redis upgrade path.
 */
export function middleware(req: NextRequest): NextResponse {
  const requestId = req.headers.get("x-request-id") || crypto.randomUUID();
  const fwd = new Headers(req.headers);
  fwd.set("x-request-id", requestId);
  const withId = (res: NextResponse): NextResponse => {
    res.headers.set("x-request-id", requestId);
    return res;
  };

  const match = rulesFor(req.method, req.nextUrl.pathname);
  if (!match) return withId(NextResponse.next({ request: { headers: fwd } }));

  const ip =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip") ||
    "unknown";
  const sessionKey = req.cookies.get(SESSION_COOKIE)?.value || ip;
  const now = Date.now();

  for (const rule of match.rules) {
    const bucketId = rule.by === "session" ? sessionKey : ip;
    const bucket = `${match.key}:${rule.windowMs}:${bucketId}`;
    const result = slidingWindow(bucket, rule, now);
    if (!result.allowed) {
      return withId(
        NextResponse.json(
          { error: "Rate limit exceeded. Please retry later." },
          {
            status: 429,
            headers: {
              "X-RateLimit-Limit": String(result.limit),
              "X-RateLimit-Remaining": "0",
              "Retry-After": String(result.retryAfterSec),
            },
          }
        )
      );
    }
  }

  // Annotate the response with headers from the tightest (last) rule.
  const res = withId(NextResponse.next({ request: { headers: fwd } }));
  const last = match.rules[match.rules.length - 1];
  res.headers.set("X-RateLimit-Limit", String(last.limit));
  return res;
}

export const config = {
  // All API routes — so every API request gets an X-Request-ID (0021); rate
  // limiting applies only where rulesFor() matches (0012). Static assets/pages
  // are excluded.
  matcher: ["/api/:path*"],
};
