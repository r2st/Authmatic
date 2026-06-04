---
id: 0033
title: Pin/reconcile bleeding-edge deps and fix version drift in docs
area: multi
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

`apps/web/package.json` runs `next@^15.1.0` and `react@^19.0.0` with
caret ranges, while README and `docs/architecture.md` describe
"Next.js 14". Caret ranges on a framework major + React 19 (recent at
build time) mean two installs can resolve to different minors, and the
docs misrepresent the stack. For a reproducible production build, deps
should be pinned and docs should match reality.

## Acceptance criteria

- [ ] Decide pinning policy (exact pins vs caret + lockfile) and apply
      consistently across `apps/web`, `apps/agent`, `packages/shared`
- [ ] `pnpm-lock.yaml` committed and `--frozen-lockfile` used in CI
      ([[0009]]) so builds are reproducible
- [ ] README + `docs/architecture.md` updated to the actual versions
      (Next 15, React 19) — or downgraded to 14/18 if 15/19 isn't
      intended for production; decide explicitly
- [ ] `apps/agent/requirements.txt` ranges reviewed; consider a lockfile
      (`pip-tools` / `uv` / `poetry.lock`) for reproducibility
- [ ] `engines` in root `package.json` (node >=20, pnpm >=9) verified
      against the deploy runtime ([[0020]])
- [ ] `pnpm audit` / `pip-audit` run once; any high-severity advisories
      triaged

## Files / surfaces

- `apps/web/package.json`
- `apps/agent/requirements.txt`
- `packages/shared/package.json`
- `README.md`
- `docs/architecture.md`

## Notes

Lower priority than the correctness/security cluster, but reproducible
builds are a prerequisite for trustworthy deploys. Bundle the doc fixes
with whoever touches [[0020]] (deploy manifests).

## Log

## Outcome
