import type { NextConfig } from "next";

// Security response headers (ticket 0024). CSP ships Report-Only first so we
// can tighten from real violation reports before enforcing; the rest are safe
// to enforce now.
const CSP_REPORT_ONLY = [
  "default-src 'self'",
  // Next injects inline runtime scripts; allow inline+eval until a
  // nonce-based middleware lands, then drop these.
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self' https:",
  // 'self' (not 'none'): the /run/[id] page frames the same-origin HealthFirst
  // portal to show live autofill. Cross-origin framing is still blocked, so
  // clickjacking protection is preserved.
  "frame-ancestors 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "report-uri /api/csp-report",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  // SAMEORIGIN (not DENY): permit the same-origin portal iframe on /run/[id]
  // while still blocking cross-origin framing.
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy-Report-Only", value: CSP_REPORT_ONLY },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  transpilePackages: ["@authmatic/shared"],
  serverExternalPackages: ["pdf-parse", "@daytonaio/sdk"],
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [
      {
        source: "/api/agent/:path*",
        destination: `${process.env.AGENT_BASE_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
