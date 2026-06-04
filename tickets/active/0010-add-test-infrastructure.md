---
id: 0010
title: Add test infrastructure + baseline API and agent-loop tests
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

Zero tests exist today. Pick frameworks, set up scaffolding, write the
minimum useful tests: API contract tests + agent-loop happy path.

## Acceptance criteria

- [ ] **Web**: Vitest configured at `apps/web/vitest.config.ts`; `pnpm --filter web test` runs
- [ ] **Web**: API route tests for every `apps/web/src/app/api/**/route.ts`: 401 without session, 404 cross-tenant, 200 happy path, 400 bad body
- [ ] **Web**: `apps/web/src/lib/submissions.ts` unit tested with a mock InsForge client
- [ ] **Agent**: `apps/agent/pyproject.toml` declares pytest + pytest-asyncio + httpx in dev deps
- [ ] **Agent**: `apps/agent/tests/test_loop.py` covers the 5-iteration happy path against fixture inputs (`DEMO_FIXTURE_MODE=true`)
- [ ] **Agent**: `apps/agent/tests/test_persist.py` covers `create_run`, `append_event`, `fetch_run_detail` against a real Postgres in `infra/docker-compose.local.yml`
- [ ] **Agent**: `apps/agent/tests/test_main.py` covers `/api/run` (400 non-pdf, 413 oversized, 401 unauthenticated after [[0005]])
- [ ] **Shared**: `packages/shared` Vitest harness ready for when types land ([[0004]])
- [ ] Tests run in CI ([[0009]]); coverage report uploaded as artifact
- [ ] Target: ≥60% line coverage on `apps/web/src/lib/` and `apps/agent/src/`

## Files / surfaces

- `apps/web/vitest.config.ts` (new)
- `apps/web/src/app/api/**/*.test.ts` (new)
- `apps/web/src/lib/**/*.test.ts` (new)
- `apps/agent/pyproject.toml`
- `apps/agent/tests/**` (new)
- `apps/agent/conftest.py` (new)

## Notes

Use fixture-mode (`DEMO_FIXTURE_MODE=true`) for agent-loop tests so
they don't need live sponsor creds in CI. Real-sponsor smoke tests
should be a separate manual workflow (`make smoke`).

## Log

## Outcome
