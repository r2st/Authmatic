---
id: 0012
title: Add rate limiting on /api/run, /api/pa/submit, and lookup endpoints
area: multi
priority: P1
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

`POST /api/run` triggers an agent ReAct loop with browser automation
(Rtrvr) and LLM calls — easily $0.10+ per call. `POST /api/pa/submit`
inserts to the DB. `GET /api/pa/[ref]` is enumerable
(see [[0007]]) — without rate limit, a script can exfiltrate every
submission. Today: no rate limit anywhere.

## Acceptance criteria

- [ ] Rate-limit middleware in `apps/web/src/middleware.ts` keyed by session (when authed) or IP
- [ ] Per-route limits documented in `apps/web/src/lib/rate-limits.ts`:
  - `POST /api/run`: 10 / clinic / minute, 200 / clinic / day
  - `POST /api/pa/submit`: 30 / clinic / minute
  - `GET /api/pa/[ref]`: 60 / session / minute
  - `GET /api/stream/[id]`: 1 active connection per run_id
  - `POST /api/auth/login`: 5 / IP / 15 minutes (brute-force defense)
- [ ] Backend: Redis (Upstash) or InsForge KV table for counters; sliding window
- [ ] Headers returned: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`
- [ ] 429 response shape standardized; never reveals other-clinic activity
- [ ] Agent service `POST /api/run` gets equivalent limit (10 / token / minute) at the FastAPI middleware layer
- [ ] CI test asserts 11th request in a minute returns 429

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
