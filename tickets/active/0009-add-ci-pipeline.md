---
id: 0009
title: Add CI — lint, typecheck, test, build on every PR
area: infra
priority: P1
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

There is no `.github/workflows/`, no `.gitlab-ci.yml`, no CI of any
kind. Every change ships untested. Add a baseline pipeline so
typecheck/lint failures don't reach main.

## Acceptance criteria

- [ ] `.github/workflows/ci.yml` runs on every PR and push to main
- [ ] Steps: `pnpm install --frozen-lockfile`, `pnpm --filter web typecheck`, `pnpm --filter web build`, `pnpm --filter web lint`
- [ ] Python steps: `pip install -r apps/agent/requirements.txt`, `ruff check apps/agent`, `mypy apps/agent`, `pytest apps/agent` (depends on [[0010]])
- [ ] Migration linter: a script that checks all `db/migrations/*.sql` files for forbidden patterns (DROP TABLE without IF EXISTS, missing transaction wrapping)
- [ ] Secret scan: `trufflehog` or `gitleaks` on every PR
- [ ] Dependency scan: `pnpm audit --prod` non-blocking, `pip-audit` non-blocking (turn blocking after initial cleanup)
- [ ] Branch protection rule documented in `docs/contributing.md`: PRs require green CI + 1 review

## Files / surfaces

- `.github/workflows/ci.yml` (new)
- `.github/workflows/migration-lint.yml` or rolled into ci.yml
- `apps/web/eslint.config.mjs` (new — none exists today)
- `apps/agent/pyproject.toml` (add ruff + mypy config)
- `docs/contributing.md` (new)

## Notes

`apps/web/package.json` has no `lint` script today. Add one (`next
lint`). Tests come in [[0010]] — the CI ticket lands the harness; the
tests land in their own ticket so this stays small.

## Log

- 2026-06-03 (claude): Added .github/workflows/ci.yml (web install/typecheck/lint/build; agent ruff/mypy/pytest; gitleaks). REMAINING: migration linter, docs/contributing.md branch-protection, Docker-image build (folds [[0020]]), drop agent mypy/pytest soft-fail once [[0010]] lands.

## Outcome
