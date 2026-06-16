---
id: 0020
title: Add deployment manifests (Render/Dockerfile) and deploy runbook
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

`README.md` and docs claim Render deploy, but there is no `render.yaml`,
no `Dockerfile`, no `Procfile`. Deploying today requires tribal
knowledge. Codify it.

## Acceptance criteria

- [ ] `apps/web/Dockerfile` — multi-stage Next.js build, runs as non-root, exposes 3000
- [ ] `apps/agent/Dockerfile` — Python slim base, runs as non-root, exposes 8000, pinned deps
- [ ] `infra/render.yaml` — service definitions for web + agent + (optional) Redis; env var stubs
- [ ] Both Dockerfiles produce reproducible images (locked deps, no `pip install` from main, no `latest` tags)
- [ ] `.dockerignore` excludes `.env`, `node_modules`, `__pycache__`, `.git`, `.venv`, `archive/`, tests
- [ ] `docs/deploy.md` runbook: how to roll out, how to roll back, how to rotate secrets, who has what access
- [ ] CI ([[0009]]) builds both images on every PR (don't push to registry on PR, do on merge to main)

## Files / surfaces

- `apps/web/Dockerfile` (new)
- `apps/agent/Dockerfile` (new)
- `infra/render.yaml` (new)
- `.dockerignore` (new)
- `docs/deploy.md` (new)
- `.github/workflows/build.yml` (new)

## Notes

If we move off Render later (Fly.io, ECS, GKE), the Dockerfiles
transfer; the `render.yaml` doesn't. Keep render-specific bits
isolated to `infra/`.

## Log

- 2026-06-03 (claude): manifests + docs landed.

## Outcome

Added `apps/web/Dockerfile` (multi-stage, Next standalone, non-root),
`apps/agent/Dockerfile` (python-slim, non-root), `infra/render.yaml`
(both services, healthCheckPath wired, secrets as `sync:false`),
`.dockerignore`, and `docs/deploy.md`. Set `output: "standalone"` in
next.config. Follow-up: building/pushing the images in CI is folded into
0009.
