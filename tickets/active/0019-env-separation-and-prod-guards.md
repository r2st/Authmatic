---
id: 0019
title: Add dev/staging/prod env separation and guards on destructive scripts
area: infra
priority: P2
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

There is one `.env` file. `scripts/reset.sh` (which wipes Postgres),
`scripts/seed.sh`, and the migrations apply against whatever
`INSFORGE_DB_URL` points at — production included. One typo and the
prod DB is reset.

## Acceptance criteria

- [ ] `.env.example` split into `.env.development.example`, `.env.staging.example`, `.env.production.example` with per-env required keys documented
- [ ] All destructive scripts (`scripts/reset.sh`, `scripts/seed.sh`, any future migrate-down) check `$INSFORGE_ENV` or hostname; refuse to run against prod unless `--i-know-what-im-doing` flag passed
- [ ] `apps/web/src/lib/insforge/admin.ts` and `apps/agent/src/settings.py` expose `IS_PRODUCTION` constant; routes that allow dangerous ops (e.g. `/api/smoke`) gate on `!IS_PRODUCTION`
- [ ] Render service config (per [[0020]]) sets `INSFORGE_ENV` explicitly per service
- [ ] Documentation: `docs/environments.md` explains the env model
- [ ] `DEMO_FIXTURE_MODE` and `USE_INPROCESS_AGENT` refuse to be true when `IS_PRODUCTION` — fail at startup, don't silently downgrade

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
