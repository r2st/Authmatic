---
id: 0015
title: Add /healthz and /readyz with dependency checks on web and agent
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

`apps/agent/main.py:131` has a trivial `/healthz` that returns ok
without checking anything; the web app has no health endpoint at all.
Render's autoscaler and uptime monitors can't tell a running-but-broken
service from a healthy one.

## Acceptance criteria

- [ ] `apps/web/src/app/api/healthz/route.ts` — process liveness (returns 200 if the Node process is up)
- [ ] `apps/web/src/app/api/readyz/route.ts` — dependency-check: InsForge SELECT 1, Tigris HEAD bucket; returns 503 if any dep is down
- [ ] Agent `/healthz` stays trivial (liveness); new `/readyz` checks DB pool, optional sponsor pings
- [ ] Render service config (per [[0020]]) wired to use `/readyz` for traffic gating, `/healthz` for restart trigger
- [ ] Endpoints are unauthenticated but lightweight; rate-limited per [[0012]] in case of probe abuse
- [ ] Documented expected response shape: `{status: "ok" | "degraded", deps: {insforge: "ok", tigris: "ok"}, version: "<git-sha>"}`
- [ ] CI smoke test: bring stack up, curl `/readyz`, assert 200 + all deps "ok"

## Files / surfaces

- `apps/web/src/app/api/healthz/route.ts` (new)
- `apps/web/src/app/api/readyz/route.ts` (new)
- `apps/agent/main.py`
- `apps/agent/src/health.py` (new)

## Notes

Don't run real sponsor pings in `/readyz` — too noisy and you'll get
rate-limited by them. `/api/smoke` (which calls each sponsor) is a
separate manual check.

## Log

- 2026-06-03 (claude): implemented all endpoints; tsc clean.

## Outcome

Web `api/healthz` (liveness) + `api/readyz` (dep-checked: InsForge query +
Tigris HeadBucket, returns 503 when any dep is down). Agent `/readyz`
(DB-pool check, 503 on failure). Both wired into `infra/render.yaml`
`healthCheckPath`. Verified `tsc --noEmit` clean. Follow-ups tracked
elsewhere: probe rate-limiting → 0012; CI readiness smoke test → 0010.
