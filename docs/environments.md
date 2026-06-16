# Environments

`AUTHMATIC_ENV` is the source of truth (falls back to `NODE_ENV`).

| Env | AUTHMATIC_ENV | DB | Demo flags allowed? |
|-----|---------------|----|--------------------|
| Local dev | `development` | local Docker Postgres (`infra/docker-compose.local.yml`) | yes |
| Staging | `staging` | InsForge staging project | discouraged |
| Production | `production` | InsForge prod project | **no — hard fail at boot** |

## Rules

- `DEMO_FIXTURE_MODE` and `USE_INPROCESS_AGENT` must be off in production.
  `apps/web/src/lib/env.ts:assertSafeForProduction()` (called from
  `instrumentation.ts`) throws at startup otherwise. The agent enforces
  the same in `apps/agent/src/settings.py`.
- Destructive scripts (`scripts/reset.sh`, `scripts/seed.sh`) refuse to
  run when `AUTHMATIC_ENV=production` unless `--force` is passed.
- Each `.env.*.example` documents the keys required per env. Copy the
  matching one to `.env` (local) or set vars in the host (staging/prod).
