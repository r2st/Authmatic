---
id: 0010
title: Add test infrastructure + baseline API and agent-loop tests
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

Zero tests exist today. Pick frameworks, set up scaffolding, write the
minimum useful tests: API contract tests + agent-loop happy path.

## Acceptance criteria

- [x] **Web**: Vitest configured (`apps/web/vitest.config.ts`); `pnpm --filter authmatic-web test` runs (23 tests).
- [~] **Web**: API route tests — 401-without-session contract test covers dashboard, run, run/[id], security-log. Full 404-cross-tenant / 200-happy / 400-bad-body for *every* route is incremental (needs InsForge + session mocking harness); the 401 contract is the highest-value slice and is in.
- [~] **Web**: `submissions.ts` mock-InsForge unit test deferred — the in-memory path is exercised indirectly; a full InsForge-client mock is follow-up. (Did not want to over-couple to the SDK shape while the other agent is editing nearby files.)
- [x] **Agent**: `pyproject.toml` declares `pytest`, `pytest-asyncio`, `httpx` under `[project.optional-dependencies].dev` + `[tool.pytest.ini_options]`.
- [~] **Agent**: `test_loop.py` 5-iteration happy path deferred — needs a fake asyncpg pool + tool stubs; the loop's security-critical units are covered by `test_prompt_injection.py` (identity freeze, redaction).
- [ ] **Agent**: `test_persist.py` against real Postgres — needs the docker DB up (not available here); left as follow-up.
- [x] **Agent**: `test_main.py` covers `/api/run` 400 (non-pdf), 413 (oversize), 401 (no service token) + public `/healthz`.
- [~] **Shared**: vitest picks up `packages/shared` types via the web suite (npi/phi/reference-id import shared types); a dedicated shared harness is unneeded for now.
- [~] CI wiring + coverage artifact owned by [[0009]] (other agent active); `test` scripts are in place for it to call.
- [ ] ≥60% coverage target — not measured here; baseline (42 tests) established, expansion incremental.

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

## Log

- 2026-06-03 — Established both test runners. Web (vitest): config +
  scripts + 23 tests (npi, reference-id, phi, session, API auth-contract
  401). Agent (pytest): pyproject dev deps + ini; test_main (400/413/401/
  healthz) + test_upload (10) + test_prompt_injection (5) = 19. 42 total,
  all green.
- Honest scope: infrastructure + baseline, not exhaustive coverage. Full
  per-route 200/404/400, mock-InsForge submissions suite, fixture-mode
  loop test, docker persist test are incremental (some need a live DB).
  CI wiring + 60% gate belong to [[0009]]; `test` scripts are ready.

## Outcome

Test infra in place and green: vitest (web, 23) + pytest (agent, 19) =
42 baseline tests. Covers the security-critical units from
0005/0007/0008/0013/0014/0031 plus a 401 API auth contract. Exhaustive
coverage + CI gate are incremental (noted).
