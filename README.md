# Authmatic

Autonomous agent that files prior authorizations on real payer portals in under
90 seconds, with a HIPAA-grade audit trail.

## Repository layout

```
.
├── apps/
│   ├── web/                Next.js 15 UI (clinic dashboard, portal, run viewer)
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

- **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind
- **Agent:** Python 3.12, FastAPI, SSE for live streaming
- **Backend:** InsForge (Postgres + Storage + Auth + Edge Functions)
- **Browser automation:** Rtrvr.ai
- **Sandbox:** Daytona
- **Object storage:** Tigris (S3-compatible)
- **Compliance scanning:** Opsera

## Database

Migrations live in `db/migrations/` (numbered `NNNN_name.sql`). They are
applied by a tracked runner — never by hand — so dev/staging/prod don't
drift. See [ADR 0006](docs/decisions/0006-migration-tool.md) for the choice.

```bash
make migrate          # apply all pending migrations (requires $INSFORGE_DB_URL)
make migrate-status   # show applied ✔ vs pending ✗
```

The runner (`scripts/migrate.sh`) records applied versions in a
`schema_migrations` table and applies each pending file in a transaction.
Add a migration by dropping a new `db/migrations/NNNN_name.sql` (continue the
numbering); never edit an applied one. In CI, the deploy job runs `make
migrate` before starting the app (see ADR 0006 + ticket 0009).

## Dependencies & reproducibility

- **Policy (ticket 0033):** caret ranges in `package.json` + a **committed
  `pnpm-lock.yaml`**; CI installs with `--frozen-lockfile` ([[0009]]) so every
  build resolves identically. The lockfile — not the range — is the
  reproducibility guarantee. The actual stack is **Next.js 15 / React 19**
  (the "14" in older docs was stale; intentionally on 15/19).
- **Agent:** `apps/agent/requirements.txt` uses bounded ranges
  (`>=x,<y`). A pinned lockfile (`pip-tools`/`uv`) is a recommended
  follow-up for byte-identical Python installs.
- **Security audit (triaged 2026-06-03):** a root `pnpm.overrides` forces
  `protobufjs >= 8.2.0`, clearing 8 advisories that came transitively
  through `@daytonaio/sdk`'s OpenTelemetry chain. One **moderate** remains
  — `postcss < 8.5.10`, bundled by Next.js, a build-time CSS tool fed only
  first-party CSS; accepted as low-risk pending a Next bump. Re-run with
  `pnpm audit --prod`.

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
