---
id: 0005
title: Replace demo auth and add server-side authz to every API route
area: multi
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

Get rid of the hackathon demo login and gate every API route with a real
server-side session check. Today **anyone with a URL can read or mutate
every clinic's PHI** — there is zero auth on any route.

## Acceptance criteria

- [x] `DEMO_USERS` deleted; `auth.ts` rewritten to client API helpers only — no passwords in source. (`scripts/seed-users.mjs` takes the password from env, never hardcodes it.)
- [x] `users` table (`0005_add_users.sql`) with scrypt-hashed passwords (`lib/auth/password.ts`). Chose scrypt over argon2id/bcrypt — memory-hard, in stdlib, no native-build risk in CI/containers. Self-describing hash format allows future rehash-on-login.
- [x] Signed, httpOnly, secure(prod), sameSite=lax cookie validated server-side (`lib/auth/session.ts` HMAC-SHA256; `getServerSession` in `lib/auth/server.ts`).
- [x] Every **clinic-facing** route gated with `getServerSession`→401: `/api/run` (POST+GET), `/api/run/[id]`, `/api/stream/[id]`, `/api/batch/[id]`, `/api/dashboard`, `/api/security-log`. **Deviation (documented):** the `/api/pa/*` routes back the *simulated public payer portal* (confirmation-number model) and stay public-by-unguessable-ref — gating them would break the portal demo and the Rtrvr headless submit. See Log.
- [x] Id routes verify clinic ownership → cross-tenant 404 + `access_denied` audit (`denyIfNotOwner`): `/api/run/[id]`, `/api/stream/[id]`, `/api/batch/[id]`. (`/api/pa/[ref]`, `/api/pa/[ref]/adjudicate` are the public payer surface — controlled by unguessable ref + rate limit, per deviation.)
- [x] Agent `main.py` bearer token (`src/auth.py` `require_service_token`, constant-time, fail-closed in prod) on `/api/run`, `/api/run/{id}`, `/api/stream/{id}`, `/api/smoke`; `/healthz` public.
- [~] Integration tests (401 + cross-tenant 404) → owned by [[0010]] (test infra). Cross-referenced; not written here.
- [x] `login/page.tsx` calls `/api/auth/login` via the rewritten `AuthProvider`; demo-credential prefill + hint removed. Added `/api/auth/login`, `/logout`, `/session`.

## Files / surfaces

- `apps/web/src/lib/auth.ts` (rewrite)
- `apps/web/src/lib/session.ts` (new — `requireSession`, `requireClinicOwns`)
- `apps/web/src/app/api/**/route.ts` (every route)
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/app/api/auth/login/route.ts` (new)
- `apps/web/src/app/api/auth/logout/route.ts` (new)
- `apps/agent/main.py`
- `apps/agent/src/auth.py` (new)
- `db/migrations/0004_add_users_and_sessions.sql` (new)

## Notes

This ticket is the single biggest gap to production. Blocks every
other auth-related ticket. Pair with [[0006]] — they should land
together to avoid a window where routes are gated but the DB still has
no tenant scoping. InsForge Auth ships a user table + JWT issuer; the
`insforge-integrations` skill covers wiring it.

## Log

- 2026-06-03 — Built the auth foundation: `lib/auth/{session,password,
  server,users}.ts`, the three `/api/auth/*` routes, `users` migration,
  and `scripts/seed-users.mjs`. Rewrote `auth.ts` + `AuthProvider` +
  login page to use the cookie-session API. Threaded `clinic_id` through
  `agent-runs`, `batch-runs`, and `submissions` so id routes can do
  ownership checks; cross-tenant access returns 404 + audit. Agent
  bearer token added. New env keys (`SESSION_SECRET`,
  `AGENT_SERVICE_TOKEN`) documented in `.env.example`. Web build + agent
  import both green.
- **Payer-vs-clinic boundary (key decision).** The codebase has two
  surfaces: the clinic dashboard (real PHI surface — now fully
  session-gated + clinic-scoped) and the `/portal/healthfirst/*` payer
  portal, a *simulated external payer* that is public by design (it's
  what Rtrvr's headless browser fills, and where a clinic checks status
  by confirmation number). The ticket's "every id route is clinic-scoped"
  assumed all routes are clinic-facing. Clinic-gating the `/api/pa/*`
  payer routes would break both the Rtrvr submit and the public status
  page. So those three routes stay public-by-unguessable-ref, with
  in-code comments marking the exception. Their controls are unguessable
  refs ([[0007]], done) + rate limiting ([[0012]]). This is a reasoned
  deviation, surfaced here rather than silently skipped.
- Tests deferred to [[0010]] (the test-infra ticket owns the harness);
  noted, not faked.
- Pairs with [[0006]] (RLS) — together they close the window where
  routes are gated but the DB has no tenant scoping. 0006 is next.

## Outcome

Zero-auth → real auth. Clinic dashboard routes require a signed
httpOnly cookie session and are clinic-scoped; cross-tenant reads 404 +
audit. Passwords are scrypt-hashed in a `users` table; demo login +
DEMO_USERS are gone. The agent service requires a service bearer token
(fail-closed in prod). The simulated payer portal stays intentionally
public-by-unguessable-ref (documented deviation). Integration tests land
with [[0010]]; DB-level tenant isolation lands with [[0006]].
