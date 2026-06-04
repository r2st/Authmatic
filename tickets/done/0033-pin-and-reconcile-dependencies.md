---
id: 0033
title: Pin/reconcile bleeding-edge deps and fix version drift in docs
area: multi
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
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

- [x] Policy decided + documented (README "Dependencies & reproducibility"): **caret ranges + committed `pnpm-lock.yaml`**, reproducibility enforced by `--frozen-lockfile` in CI — the lockfile, not the range, is the guarantee. Avoids churning every dep (and colliding with [[0032]]'s package.json edits).
- [x] `pnpm-lock.yaml` committed; `--frozen-lockfile` for CI documented (cross-ref [[0009]]).
- [x] Docs reconciled to reality: README (×2) + CLAUDE.md → **Next.js 15 / React 19** (resolved 15.5.18 / 19.2.6). Decision: stay on 15/19 (build is green). architecture.md had no version claim to change.
- [~] `requirements.txt` ranges are already bounded (`>=x,<y`); a pip lockfile (pip-tools/uv) recommended as a follow-up (noted in README) — not adopted now to avoid a second Python toolchain mid-flight.
- [x] `engines` (node >=20, pnpm >=9) verified present + consistent with the deploy runtime; cross-ref [[0020]].
- [x] `pnpm audit --prod` run + triaged: added root `pnpm.overrides protobufjs>=8.2.0` → cleared **8 of 9** advisories (4 high + 4 moderate, all transitive via `@daytonaio/sdk`). Remaining 1 moderate = build-time `postcss<8.5.10` bundled by Next, first-party CSS only → accepted, documented. (`pip-audit` is a follow-up alongside the Python lockfile.)
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

- 2026-06-03 (claude): grype critical/high triage (from the pre-commit scan that showed 6 critical / 28 high). Found 33 of 34 were the @esbuild dev/build binary (Go stdlib CVEs) — NOT in the production image; added .grype.yaml to ignore them with a documented reason (65 noise matches dropped → scan now shows 1 critical + 1 high, the real signal). Remaining: (1) vitest@2.1.9 CRITICAL GHSA-5xrq-8626-4rwp — dev-only test runner, not shipped; fix is vitest 4.x (major, would break test config) — recommend bumping when test compat is verified. (2) starlette@0.46.2 HIGH GHSA-7f5h-v6xp-fcq8 (multipart DoS — relevant: agent accepts PDF uploads) — the ONE shipped CVE; cannot bump minimally because FastAPI 0.115 pins starlette<0.47, so the fix requires fastapi 0.115->0.136 + starlette 0.46->1.x (a major framework jump incl. sse-starlette compat) that MUST be done with the agent runnable + integration-tested. NOT blind-applied. Recommend a dedicated P1 ticket for the FastAPI/starlette upgrade.

## Outcome

## Log

- 2026-06-03 — Policy: caret + committed lockfile + `--frozen-lockfile`
  (lockfile is the reproducibility guarantee). Reconciled docs to Next
  15 / React 19 (README ×2 + CLAUDE.md). Ran `pnpm audit --prod`: added
  root `pnpm.overrides` forcing `protobufjs>=8.2.0`, dropping the count
  from 9 (4 high) to 1 moderate (build-time postcss via Next, accepted).
  Did NOT edit apps/web/package.json deps (caret policy needs none) —
  avoids colliding with the other agent's [[0032]] edits.
- Follow-ups noted in README: Python lockfile (pip-tools/uv) + pip-audit.

## Outcome

Reproducibility policy decided + documented (caret + frozen lockfile);
docs now state the real stack (Next 15 / React 19). Security audit
triaged with a real fix — a protobufjs override clears 8 of 9
advisories; the lone remaining one is a low-risk build-time postcss
issue, documented and accepted.
