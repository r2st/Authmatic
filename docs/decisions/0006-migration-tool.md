# ADR 0006 — Database migration tool

- **Status:** accepted
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0003-adopt-migration-tool.md
- **Related:** [ADR 0005 data model](0005-data-model-boundary.md)

## Context

Migrations were applied by hand: `psql -f db/migrations/000N_*.sql`, one at a
time, with nothing tracking which file had run against which environment.
That drifts dev/staging/prod and invites double-applies or skips. We need a
tool that records applied migrations and applies only what's pending — before
the schema grows further.

## Options considered

| Tool | Fit | Cost |
|---|---|---|
| **golang-migrate / dbmate** | Good trackers | Require `.up.sql/.down.sql` pairs or `-- migrate:up` markers → must edit/rename all 8 existing, already-applied migrations (violates "never edit an applied migration", rule 6) + a new binary dependency |
| **Atlas** | Powerful (declarative/versioned) | Heavy; HCL config; overkill for a hackathon-scale schema; new binary |
| **Prisma migrate** | Nice DX | Pulls in Prisma ORM + a schema.prisma we don't otherwise use |
| **InsForge CLI** | Native to our backend | Couldn't verify its migration-dir format/behavior from here; ties the runner to one provider |
| **Minimal psql runner (chosen)** | Runs the existing plain `NNNN_*.sql` files unchanged | Tiny custom script; no version-skew niceties of a big tool |

## Decision

Adopt a **dependency-free `psql`-based runner** — `scripts/migrate.sh` —
with `make migrate` / `make migrate-status` targets.

- Tracks applied migrations in a `schema_migrations(version, applied_at)`
  table (created on first run).
- Applies pending `db/migrations/NNNN_*.sql` in filename order, each file +
  its bookkeeping row in a single transaction (`--single-transaction`,
  `ON_ERROR_STOP=1`).
- Uses the existing files **unchanged** — no `.up/.down` rename, no markers,
  so rule 6 ("never edit an applied migration") holds. The filename stem is
  the version id.
- Needs only `psql`, which InsForge Postgres already speaks — no new binary,
  no provider lock-in.

### Why a custom runner over a "real" tool

The dominant cost of golang-migrate/dbmate/Atlas here is forcing edits to 8
already-applied migrations or adding an unpinnable binary to every CI/dev/
prod image. The runner is ~60 lines, transactional, idempotent, and CI-
trivial. If the schema later needs down-migrations, branching, or
checksumming, revisit and graduate to dbmate (the markers can be added then).

## CI hook (documented; wire in [[0009]])

Staging/prod deploy runs migrations before the app starts:

```yaml
# in the deploy job, after checkout, with INSFORGE_DB_URL set for the env:
- run: make migrate            # applies pending migrations, fails the deploy on error
```

Run `make migrate-status` in a pre-deploy check to surface drift. Never run
`make migrate` against prod from a developer machine — only from the deploy
pipeline with the prod `INSFORGE_DB_URL` (see [[0019]] prod guards).

## Consequences

- One command (`make migrate`) brings any environment up to date; `make
  migrate-status` shows applied vs pending.
- The runner is forward-only (no `down`). Rollbacks are a new compensating
  migration — appropriate for a PHI DB where down-migrations risk data loss.
- New migrations: drop a `db/migrations/NNNN_name.sql` file; the runner picks
  it up. Numbering continues from the highest existing file.
