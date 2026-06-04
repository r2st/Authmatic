# Deploy runbook

Authmatic ships two services: `authmatic-web` (Next.js) and
`authmatic-agent` (FastAPI). Both are Docker images; the canonical
blueprint is [`infra/render.yaml`](../infra/render.yaml).

## Prerequisites

- Render account with the blueprint imported, OR any Docker host.
- Secrets set per [secrets-rotation.md](secrets-rotation.md) — never in git.
- Database migrations applied (see [the migration tool, ticket 0003]).

## Build

```bash
docker build -f apps/web/Dockerfile   -t authmatic-web   .
docker build -f apps/agent/Dockerfile -t authmatic-agent .
```

Both build from the repo root (`dockerContext: .`) so the web image can
see `packages/shared` and the agent image can see `fixtures/`.

## Roll out

1. Merge to `main` → CI green ([.github/workflows/ci.yml](../.github/workflows/ci.yml)).
2. `autoDeploy: false` — promote manually in Render after CI passes.
3. Apply any pending DB migrations BEFORE promoting web/agent.
4. Watch `/api/readyz` (web) and `/readyz` (agent) — they gate traffic.

## Roll back

- Render: "Rollback" to the previous deploy in the dashboard.
- DB: migrations are forward-only; a rollback of code must be compatible
  with the live schema. Never auto-run down-migrations in prod.

## Health endpoints

| Service | Liveness | Readiness (dep-checked) |
|---------|----------|-------------------------|
| web     | `/api/healthz` | `/api/readyz` (InsForge + Tigris) |
| agent   | `/healthz` | `/readyz` (DB pool) |

## Environments

`AUTHMATIC_ENV` ∈ {development, staging, production} drives behavior. In
production, demo flags (`DEMO_FIXTURE_MODE`, `USE_INPROCESS_AGENT`) cause
a hard startup failure (see `apps/web/src/lib/env.ts`). See
[environments.md](environments.md).
