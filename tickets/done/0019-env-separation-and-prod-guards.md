---
id: 0019
title: Add dev/staging/prod env separation and guards on destructive scripts
area: infra
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

There is one `.env` file. `scripts/reset.sh` (which wipes Postgres),
`scripts/seed.sh`, and the migrations apply against whatever
`INSFORGE_DB_URL` points at — production included. One typo and the
prod DB is reset.

## Acceptance criteria

- [x] `.env.example` split into `.env.development/staging/production.example` with per-env required keys + secret-source notes.
- [x] `reset.sh` + `seed.sh` refuse when `AUTHMATIC_ENV=production` unless `--force`.
- [x] `settings.py` exposes `is_production`; `admin.ts` now exposes `IS_PRODUCTION`/`AUTHMATIC_ENV`. (Agent `/api/smoke` is already service-token-gated ([[0005]]); no web dangerous-op route to gate.)
- [~] Render `AUTHMATIC_ENV` per service → [[0020]] (done); cross-ref.
- [x] `docs/environments.md` documents the env model.
- [x] `DEMO_FIXTURE_MODE` **and** `USE_INPROCESS_AGENT` fail at startup in prod (`assert_safe_for_production` in the agent lifespan). Added the `use_inprocess_agent` field + guard (was fixture-only); verified it raises.

## Files / surfaces

- `.env.development.example`, `.env.staging.example`, `.env.production.example` (new)
- `scripts/reset.sh`
- `scripts/seed.sh`
- `scripts/seed.py`
- `apps/web/src/lib/env.ts` (new)
- `apps/agent/src/settings.py`
- `apps/agent/main.py` (gate /api/smoke)
- `docs/environments.md` (new)

## Notes

Pairs with [[0003]] (migration tool) — env separation is most
load-bearing for migrations.

The `DEMO_FIXTURE_MODE` / `USE_INPROCESS_AGENT` prod-refusal guards in
this ticket are the safety net for the demo-theater cluster
([[0025]], [[0029]], [[0030]], [[0031]]): those tickets gate fixture
data and scripted paths behind `DEMO_FIXTURE_MODE`, and THIS ticket is
what guarantees that flag can't be true in production. Land the guard
early so the cluster has somewhere safe to hide its demo paths.
Note `.env.example` defines `DEMO_FIXTURE_MODE` twice — dedupe while
splitting per-env files.

## Log

- 2026-06-03 (claude): Added env.ts + instrumentation.ts guard (web) and settings.assert_safe_for_production (agent) refusing demo flags in prod; reset.sh/seed.sh refuse prod without --force; docs/environments.md. REMAINING: split .env.development/staging/production.example files; dedupe duplicate DEMO_FIXTURE_MODE in .env.example.

## Outcome

## Log

- 2026-06-03 — Taken over from a stalled session that had added the
  env machinery + script prod-guards + docs/environments.md. Filled
  gaps: split env examples into dev/staging/prod, added IS_PRODUCTION to
  web admin.ts, extended the startup assert to refuse USE_INPROCESS_AGENT
  in prod (was fixture-only). Verified the guard raises; ruff clean.

## Outcome

Three-environment model with prod guards: destructive scripts refuse in
prod, the agent fails fast at startup on any demo shortcut in production,
both services expose is_production/IS_PRODUCTION, and per-env
.env.*.example files document required keys.
