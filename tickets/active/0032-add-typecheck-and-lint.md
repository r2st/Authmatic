---
id: 0032
title: Add typecheck + lint scripts and an ESLint config
area: web
priority: P1
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

`apps/web/package.json` has no `lint` and no `typecheck` script, and
there is no ESLint config file in the tree. TypeScript `strict` is on
(good) but nothing runs `tsc --noEmit` in any automated way, so type
errors only surface during `next build`. Lint isn't enforced at all.

## Acceptance criteria

- [ ] `apps/web/package.json` gains `"typecheck": "tsc --noEmit"` and
      `"lint": "next lint"` (or `eslint .`)
- [ ] ESLint config added (`apps/web/eslint.config.mjs`) extending
      `next/core-web-vitals` + `@typescript-eslint` recommended
- [ ] Rules that catch real bugs enabled: `no-floating-promises`
      (catches the `void runAgentPipeline` class of issues),
      `no-misused-promises`, `no-explicit-any` (warn)
- [ ] `noUncheckedIndexedAccess` considered for tsconfig (the code does
      `data![0]`, `split(" ")[0]` in several places without guards)
- [ ] Python side: `ruff` + `mypy` config in `apps/agent/pyproject.toml`
      with `ruff check` and `mypy apps/agent` scripts
- [ ] Existing violations fixed or explicitly baseline-ignored with a
      tracking note
- [ ] Wired into CI ([[0009]]) as required gates

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
