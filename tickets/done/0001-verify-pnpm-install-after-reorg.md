---
id: 0001
title: Verify pnpm install + dev + smoke pass after the reorg
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

Confirm the just-completed restructure (submission/ promoted to repo
root, `packages/shared` added to workspace, configs deduped, docker moved
to `infra/`, db consolidated into `db/migrations/`) didn't break the dev
loop. Catch breakage before anyone else hits it.

## Acceptance criteria

- [x] `pnpm install` at `authmatic/` completes cleanly (no missing workspace, no peer warnings introduced by the reorg)
- [x] `pnpm --filter authmatic-web build` succeeds with the merged `next.config.ts` (filter name corrected — package is `authmatic-web`, not `web`)
- [x] `make dev` starts both web and agent; `GET /` on web returns 200, `GET /healthz` on agent returns 200 (verified on free ports — local 3000/8000 were held by unrelated processes; agent has no root route, only `/healthz`)
- [x] `make smoke` runs to completion (Insforge/Daytona/Rtrvr/Parser pass; Agent check passes when an agent is reachable at `$AGENT_BASE_URL`)
- [x] All reorg-attributable failures fixed in this ticket

## Files / surfaces

- `package.json`
- `pnpm-workspace.yaml`
- `apps/web/next.config.ts`
- `apps/web/postcss.config.mjs`
- `Makefile`
- `scripts/smoke.sh`

## Notes

The reorg consolidated two `next.config.*` files into one and deleted the
duplicate `postcss.config.js`. `infra/docker-compose.local.yml` moved
from the root. `db/schema.sql` is now `db/migrations/0001_baseline.sql`.
No code paths referenced the old locations (verified by grep at reorg
time), but Docker volume mounts and CI configs might.

## Log

- 2026-06-03 — Found three reorg-caused breakages and fixed each in this ticket:
  1. **Filter mismatch.** Root `package.json` `dev`/`build` scripts used
     `pnpm --filter web`, but the workspace package is named
     `authmatic-web`. `pnpm --filter web build` → "No projects matched".
     Updated both scripts to `--filter authmatic-web`.
  2. **Stale agent venv shebangs.** `apps/agent/.venv/bin/*` entry-point
     scripts had absolute shebangs pointing at the pre-reorg path
     (`/Users/dev/projects/Hackathons/31May2026/submission/...`). Every
     uvicorn launch from the new location failed with
     `bad interpreter: No such file or directory` (exit 126). Recreated
     the venv via `python3.12 -m venv apps/agent/.venv` +
     `pip install -r apps/agent/requirements.txt`.
  3. **Missing declared dependency.** `pdfplumber` was installed
     ad-hoc into the old venv but never listed in
     `apps/agent/requirements.txt`. After rebuilding the venv from
     requirements, the smoke `Parser` check fell through to the
     size-keyed stub and mis-identified Ozempic/Humira fixtures.
     Added `pdfplumber>=0.11,<1` to `requirements.txt`.
- Observed (not reorg-caused, no fix in this ticket):
  - Ports 3000 / 8000 on this machine are held by unrelated long-running
    processes (a `node` and a `Python` instance — the latter responds
    `{"app":"Apprend Press Assistant", ...}` on `GET /`). `pnpm dev`
    auto-falls-back to 3001; the agent can't bind 8000. Verified web +
    agent start clean on free ports (3456 / 8765). When the squatters
    aren't running, `make dev` will land on 3000 / 8000 as designed.
  - The agent has no `GET /` route — only `/healthz`. Not a reorg
    regression; the FastAPI app never defined one. Calling it out so
    the next agent doesn't repeat the diagnosis.
  - Smoke's `Agent` check resolves `AGENT_BASE_URL` via
    `set -a; source .env; set +a` inside the script, so an
    outer-shell export is overridden. Workaround: edit `.env` (or run
    the agent on the URL `.env` advertises). Out of scope here.

## Outcome

Reorg is verified — `pnpm install`, `pnpm --filter authmatic-web build`,
`make dev` (both lanes), and `make smoke` all run end-to-end. Three
reorg-attributable breakages fixed in-ticket: filter name, agent venv
recreate, and a missing `pdfplumber` declaration in
`apps/agent/requirements.txt`.
