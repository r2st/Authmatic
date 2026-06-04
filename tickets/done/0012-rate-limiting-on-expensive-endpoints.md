---
id: 0012
title: Add rate limiting on /api/run, /api/pa/submit, and lookup endpoints
area: multi
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

`POST /api/run` triggers an agent ReAct loop with browser automation
(Rtrvr) and LLM calls — easily $0.10+ per call. `POST /api/pa/submit`
inserts to the DB. `GET /api/pa/[ref]` is enumerable
(see [[0007]]) — without rate limit, a script can exfiltrate every
submission. Today: no rate limit anywhere.

## Acceptance criteria

- [x] `apps/web/src/middleware.ts` — keyed per-session (signed cookie value, opaque bucket id) or per-IP; matcher scopes it to the limited routes.
- [x] Per-route limits in `lib/rate-limits.ts`: run 10/min + 200/day, pa/submit 30/min, pa/[ref] lookup 60/min, login 5/15min. (run/day uses session key; submit/lookup use IP per the "session-or-IP" rule.)
  - [~] `/api/stream/[id]` "1 active connection per run_id" is a concurrency limit, not a sliding window — left as a follow-up (needs connection tracking, not a counter); noted in `rate-limits.ts`.
- [x] Sliding-window backend, in-process. Redis/Upstash/InsForge-KV upgrade path documented (same interface, swap `slidingWindow`).
- [x] `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` headers on 429.
- [x] 429 body is generic ("Rate limit exceeded. Please retry later.") — reveals nothing about other clinics; bucket is the caller's own.
- [x] Agent `POST /api/run` gets 10/token/minute (`src/ratelimit.py`, FastAPI dependency alongside the service token).
- [x] Tests assert the 11th request → 429: web `rate-limits.test.ts` (7) + agent `test_ratelimit.py` (2). All pass.

## Files / surfaces

- `apps/web/src/middleware.ts` (new or extend existing)
- `apps/web/src/lib/rate-limits.ts` (new)
- `apps/web/src/lib/rate-limiter.ts` (new)
- `apps/agent/main.py`
- `apps/agent/src/rate_limit.py` (new)

## Notes

A WAF (Cloudflare, Render's built-in) is a defense-in-depth layer above
the app limits — document the expectation in the ADR but don't depend
on it solely.

## Log

## Outcome

## Log

- 2026-06-03 — `lib/rate-limits.ts` (config + edge-safe sliding window),
  `middleware.ts` (per-session/IP, 429 + headers; cookie name inlined so
  the edge bundle avoids node:crypto), agent `src/ratelimit.py` (FastAPI
  dep, 10/token/min). 9 tests across web+agent pass; typecheck clean;
  agent imports clean.
- Note: the `next build` lint gate currently fails on PRE-EXISTING
  type-aware-lint debt across the repo (the other agent's 0009/0032
  strict ESLint config) — unrelated to this ticket. Verified my code via
  `tsc --noEmit` + the test suites instead; made my new logout route
  lint-clean.
- `/api/stream` per-connection cap deferred (concurrency, not a counter).

## Outcome

Rate limiting live on the expensive/abusable endpoints: web middleware
(run 10/min+200/day, submit 30/min, lookup 60/min, login 5/15min) and
the agent `/api/run` (10/token/min), both sliding-window with standard
429 headers and a leak-free body. In-process now; Redis upgrade path
documented. 9 passing tests including the 11th-request-429 assertion.
