# Gulnoza integration → merge into r2st/Authmatic

Branch: `GulnozaU/Authmatic:gulnoza/final-integration`

## Open PR manually

https://github.com/r2st/Authmatic/compare/main...GulnozaU:Authmatic:gulnoza/final-integration

Ask Subhendu to merge, or add Gulnoza as collaborator on `r2st/Authmatic`.

## What's included

| Feature | Files |
|---------|--------|
| Real PA form (Form HF-PA-212 layout) | `apps/web/src/components/portal/PriorAuthForm.tsx`, `portal-form-data.ts` |
| 3 demo patients | `apps/web/src/lib/demo-cases.ts`, `demo/*.json` |
| Parallel batch runs | `apps/web/src/app/batch/`, `api/batch/`, home page |
| Submission receipt links | relative URLs, dashboard links |
| Tigris + InsForge persist | existing `tigris/`, `submissions.ts` |
| Rtrvr + Opsera + Daytona | `apps/web/src/lib/sponsors/` |
| Portal handoff spec | `fixtures/insurance/healthfirst/portal-spec.json` |

## Demo flow (local)

```bash
cd apps/web && npm run dev
```

1. **/** — pick scenario or "Run batch (2 patients)"
2. **/run/{id}** — agent audit + iframe autofill
3. **/portal/healthfirst/submission/PA-...** — submission receipt
4. **/dashboard** — click reference IDs to view submissions

## Env (production)

```
DEMO_FIXTURE_MODE=true
WEB_URL=https://your-insforge.site
PORTAL_URL=https://your-insforge.site/portal/healthfirst/prior-auth
RTRVR_API_KEY=...
INSFORGE_* , TIGRIS_*
```

## Architecture note

This fork uses an **in-process Next.js agent** (`agent-orchestrator.ts`) instead of FastAPI. After merge, either:

- Keep both (web proxies to agent in prod), or
- Port batch + demo cases into `apps/agent` Python loop

The portal form and demo cases are portable to either stack.
