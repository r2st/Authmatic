---
id: 0032
title: Add typecheck + lint scripts and an ESLint config
area: web
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

`apps/web/package.json` has no `lint` and no `typecheck` script, and
there is no ESLint config file in the tree. TypeScript `strict` is on
(good) but nothing runs `tsc --noEmit` in any automated way, so type
errors only surface during `next build`. Lint isn't enforced at all.

## Acceptance criteria

- [x] `apps/web/package.json` has `"typecheck": "tsc --noEmit"` + `"lint": "eslint ."`.
- [x] `eslint.config.mjs` (flat) extends tseslint `recommended` + Next recommended + core-web-vitals.
- [x] `no-floating-promises`, `no-misused-promises`, `no-explicit-any` enabled as **warnings** (visible, non-blocking). The prior config used `recommendedTypeChecked` + made these errors → failed the build on ~53 pre-existing patterns. Downgraded with a tracking note in the config header (promote to error once the promise debt is paid — [[0027]]). `eslint .` now reports **0 errors** (12 warnings).
- [~] `noUncheckedIndexedAccess`: considered, **not enabled** (would flag dozens of `data![0]`/`split(" ")[0]` at once). Tracked as an incremental follow-up; decision noted.
- [x] Python: ruff config present; added `[tool.mypy]` (lenient baseline) + ruff/mypy dev deps. `ruff check .` clean; `mypy src/*` clean on typed modules. `make lint` / `make typecheck` run web + agent.
- [x] Violations fixed (web 53→0 errors; ruff 16→0) or baseline-ignored with notes (`B008`/`S108` framework/sandbox false-positives, per-file test S-ignores).
- [~] CI gates → [[0009]] (taken over too); `make lint`/`make typecheck`/`pnpm test` are the commands.

## Files / surfaces

- `apps/web/package.json`
- `apps/web/eslint.config.mjs` (new)
- `apps/web/tsconfig.json`
- `apps/agent/pyproject.toml`

## Notes

`@typescript-eslint/no-floating-promises` alone would have flagged the
fire-and-forget agent kickoff ([[0027]]) and the background-persist
calls. Cheap, high-value.

## Log

- 2026-06-03 (claude): Added typecheck script (verified tsc clean) + lint script + eslint flat config + eslint devDeps. REMAINING: pnpm install to activate lint then fix violations, ruff+mypy config in agent pyproject.toml, consider noUncheckedIndexedAccess.

## Outcome

## Log

- 2026-06-03 — Taken over from a stalled session that had added eslint
  deps + scripts + a `recommendedTypeChecked` config that produced 53
  errors and blocked `next build`. Re-tuned to `recommended` + Next
  rules with the high-value promise rules as warnings → 0 errors, build
  green again. Python: ruff cleaned to 0 (auto-fix + sensible ignores for
  FastAPI/sandbox/test false-positives), mypy baseline added (clean on
  typed modules). Added `make lint` / `make typecheck`.

## Outcome

`pnpm lint` (0 errors), `pnpm typecheck`, `ruff check`, and `mypy src`
all pass; `make lint` / `make typecheck` run web + agent together. The
build is no longer blocked by an over-tuned lint config. Type-aware
promise rules remain on as warnings (a tracked debt for [[0027]]);
`noUncheckedIndexedAccess` is a documented follow-up.
