/**
 * Rate-limit configuration + a sliding-window limiter (ticket 0012).
 *
 * Backend: in-process sliding window. This is per-instance — correct on a
 * single node, approximate across a horizontally-scaled deployment. For
 * production multi-instance accuracy, swap `slidingWindow` for an Upstash
 * Redis / InsForge-KV implementation behind the same interface (the call
 * sites in middleware.ts don't change). Documented as the upgrade path.
 *
 * Edge-safe: no node-only APIs, so it runs in Next middleware.
 */

export interface RateRule {
  /** Max requests allowed within the window. */
  limit: number;
  /** Window length in milliseconds. */
  windowMs: number;
  /** Bucket key source: per session cookie, or per client IP. */
  by: "session" | "ip";
}

const MINUTE = 60_000;
const DAY = 24 * 60 * MINUTE;

/**
 * Per-route limits. A request matching multiple rules must satisfy ALL of
 * them (e.g. /api/run is both per-minute and per-day). Keyed by `${METHOD}
 * ${pathPrefix}`.
 */
export const RATE_LIMITS: Record<string, RateRule[]> = {
  "POST /api/run": [
    { limit: 10, windowMs: MINUTE, by: "session" },
    { limit: 200, windowMs: DAY, by: "session" },
  ],
  "POST /api/pa/submit": [{ limit: 30, windowMs: MINUTE, by: "ip" }],
  "GET /api/pa": [{ limit: 60, windowMs: MINUTE, by: "ip" }], // /api/pa/[ref] lookup
  "POST /api/auth/login": [{ limit: 5, windowMs: 15 * MINUTE, by: "ip" }],
};

/** Resolve the rules for a request, or null if the route is unlimited. */
export function rulesFor(method: string, pathname: string): { key: string; rules: RateRule[] } | null {
  // Exact-ish prefix match, longest first so /api/pa/submit beats /api/pa.
  const candidates = Object.keys(RATE_LIMITS)
    .filter((k) => {
      const [m, p] = k.split(" ");
      return m === method && pathname.startsWith(p);
    })
    .sort((a, b) => b.length - a.length);
  if (!candidates.length) return null;
  const key = candidates[0];
  return { key, rules: RATE_LIMITS[key] };
}

// ─── sliding-window store ────────────────────────────────────────────
type Hits = number[]; // sorted ascending timestamps (ms)
const store = new Map<string, Hits>();

export interface LimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  retryAfterSec: number;
}

/**
 * Sliding-window check-and-record for one (bucketKey, rule). Records the hit
 * when allowed; on denial returns the seconds until the window frees up.
 */
export function slidingWindow(bucketKey: string, rule: RateRule, now: number): LimitResult {
  const windowStart = now - rule.windowMs;
  const hits = (store.get(bucketKey) ?? []).filter((t) => t > windowStart);

  if (hits.length >= rule.limit) {
    const oldest = hits[0];
    const retryAfterSec = Math.max(1, Math.ceil((oldest + rule.windowMs - now) / 1000));
    store.set(bucketKey, hits);
    return { allowed: false, limit: rule.limit, remaining: 0, retryAfterSec };
  }

  hits.push(now);
  store.set(bucketKey, hits);
  return { allowed: true, limit: rule.limit, remaining: rule.limit - hits.length, retryAfterSec: 0 };
}

/** Test/maintenance helper — clear all buckets. */
export function _resetRateLimits(): void {
  store.clear();
}
