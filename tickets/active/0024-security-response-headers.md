---
id: 0024
title: Add security response headers (CSP, HSTS, X-Frame, etc.)
area: web
priority: P2
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

Next.js ships no security headers by default. Today the responses have
no CSP, no HSTS, no X-Frame-Options, no Referrer-Policy. The
`/portal/healthfirst/*` flow renders user-influenced submission data —
without CSP, an XSS injection (from a malformed `justification` or
similar field) executes freely.

## Acceptance criteria

- [ ] `apps/web/next.config.ts` `headers()` block adds:
  - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
  - `Content-Security-Policy` — strict, with nonce-based script-src; report-only mode first for a week, then enforced
  - `X-Frame-Options: DENY` (or CSP `frame-ancestors 'none'`)
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy` — disable camera/microphone/geolocation by default
- [ ] CSP allowlist: self, InsForge SDK origin, Tigris (if frontend reads), no `unsafe-inline` (use nonces)
- [ ] CSP violation report endpoint (`/api/csp-report`) that logs to the observability stack ([[0011]])
- [ ] All `dangerouslySetInnerHTML` audited and removed where possible; remaining instances justified inline
- [ ] Tests assert headers on `/`, `/dashboard`, `/portal/healthfirst/prior-auth`, `/api/healthz`

## Files / surfaces

- `apps/web/next.config.ts`
- `apps/web/src/middleware.ts` (CSP nonce injection)
- `apps/web/src/app/api/csp-report/route.ts` (new)

## Notes

CSP is the highest-value header for an app this size. Roll out in
report-only mode first; production-grade CSP rules take iteration.

## Log

- 2026-06-03 (claude): Added security headers in next.config.ts (HSTS, X-Frame DENY, nosniff, Referrer-Policy, Permissions-Policy) + CSP Report-Only + api/csp-report route. Verified tsc clean. REMAINING: nonce-based ENFORCED CSP via middleware, dangerouslySetInnerHTML audit, header tests.

## Outcome
