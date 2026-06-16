---
id: 0009
title: Add CI — lint, typecheck, test, build on every PR
area: infra
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

There is no `.github/workflows/`, no `.gitlab-ci.yml`, no CI of any
kind. Every change ships untested. Add a baseline pipeline so
typecheck/lint failures don't reach main.

## Acceptance criteria

- [x] `.github/workflows/ci.yml` runs on every PR + push to main.
- [x] Web job: `pnpm install --frozen-lockfile` → typecheck → lint → **test** → build → audit. **Fixed the filter-name bug** (`--filter web` → `authmatic-web`, which would have failed every run) + pnpm 9→10 to match the lockfile.
- [x] Agent job: install `requirements.txt` + `.[dev]` → `ruff check` → `mypy src` (lenient baseline) → `pytest` (the stale `|| true` guards dropped now that [[0010]] tests exist).
- [x] Migration linter: `scripts/lint-migrations.sh` (own CI job) — rejects `DROP` without `IF EXISTS`, `TRUNCATE`, `DELETE` without `WHERE`. Runs clean on the 8 current migrations.
- [x] Secret scan: gitleaks job over full history.
- [x] Dependency scan: `pnpm audit --prod` + `pip-audit`, both non-blocking (`|| true`) per the "turn blocking after cleanup" note.
- [x] Branch protection documented in `docs/contributing.md` (green CI + 1 review + up-to-date), with the GitHub-settings step flagged ACTION REQUIRED.

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

## Log

- 2026-06-03 — Taken over from a stalled session that drafted ci.yml.
  Fixed the `--filter web` → `authmatic-web` bug (would fail every run),
  bumped pnpm to 10 (lockfile format), dropped the stale `|| true` on
  pytest (0010 tests exist), added a `migrations` job (new
  `scripts/lint-migrations.sh`, clean on 8 files) + non-blocking
  dependency audits, and wrote `docs/contributing.md` with branch
  protection. ci.yml validated as well-formed YAML.

## Outcome

Full CI pipeline on every PR/push: web (install/typecheck/lint/test/
build/audit), agent (ruff/mypy/pytest/pip-audit), migration lint, and
gitleaks. Branch-protection policy documented (the GitHub-settings toggle
is the one human ACTION REQUIRED).
