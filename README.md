# Authmatic

Autonomous agent that files prior authorizations on real payer portals in under
90 seconds, with a HIPAA-grade audit trail.

## Repository layout

```
.
├── apps/
│   ├── web/                Next.js 14 UI (clinic dashboard, portal, run viewer)
│   └── agent/              FastAPI agent service (READ-WEB → EXTRACT → SUBMIT → PERSIST)
├── packages/
│   └── shared/             Shared TS types (placeholder)
├── db/
│   └── migrations/         Numbered SQL migrations (0001_baseline.sql is the starting schema)
├── fixtures/               HealthFirst portal + case fixtures
│   ├── healthfirst-case.json
│   ├── healthfirst-portal.json
│   └── insurance/          Per-payer portal specs
├── infra/
│   └── docker-compose.local.yml   Local Postgres + pgvector for offline dev
├── scripts/                Seed, smoke, reset, PDF generation
├── assets/                 Demo PDFs, sponsor fixtures
├── demo/                   Pitch script, recordings, presentation.html
├── docs/                   Architecture, sponsor notes, handoff docs
└── archive/                Hackathon coordination artifacts (frozen, do not edit)
```

## Quick start

```bash
cp .env.example .env                   # fill in keys
make install                           # pnpm + pip dependencies
make seed                              # populate Postgres with demo patients
make dev                               # web on :3000, agent on :8000
```

`make smoke` runs a hello-world check against each sponsor integration.

## Stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind
- **Agent:** Python 3.12, FastAPI, SSE for live streaming
- **Backend:** InsForge (Postgres + Storage + Auth + Edge Functions)
- **Browser automation:** Rtrvr.ai
- **Sandbox:** Daytona
- **Object storage:** Tigris (S3-compatible)
- **Compliance scanning:** Opsera

## Database

Migrations live in `db/migrations/`. Apply with:

```bash
psql "$INSFORGE_DB_URL" -f db/migrations/0001_baseline.sql
psql "$INSFORGE_DB_URL" -f db/migrations/0002_add_pa_submissions.sql
psql "$INSFORGE_DB_URL" -f db/migrations/0003_add_pa_submissions_review_cols.sql
```

For sustained development, wire these into a migration tool (Atlas, sqlx,
golang-migrate, or InsForge's own CLI).

## Documentation

- [docs/architecture.md](docs/architecture.md) — system design narrative
- [docs/architecture-overview.md](docs/architecture-overview.md) — ASCII diagram + flow
- [docs/spec.md](docs/spec.md) — agent loop spec
- [docs/implementation.md](docs/implementation.md) — implementation notes
- [docs/risks.md](docs/risks.md) — known risks + fallbacks
- [docs/insforge.md](docs/insforge.md), [docs/tigris.md](docs/tigris.md) — sponsor integration notes
- [docs/healthfirst-portal-handoff.md](docs/healthfirst-portal-handoff.md) — portal spec

## License

MIT — see [LICENSE](LICENSE).
