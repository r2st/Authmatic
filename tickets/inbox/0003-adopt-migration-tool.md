---
id: 0003
title: Adopt a real migration tool for db/migrations/
area: db
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: [0002]
---

## Goal

Replace "run psql by hand" with a tool that tracks which migrations have
been applied to which environment. Picking a tool now, before the schema
grows further, prevents drift between dev/staging/prod.

## Acceptance criteria

- [ ] Decision recorded as an ADR (`docs/decisions/0006-migration-tool.md`) — picked tool + rationale (Atlas / sqlx / golang-migrate / InsForge CLI / Prisma migrate / etc.)
- [ ] Tool configured against the existing `db/migrations/0001*.sql`, `0002*.sql`, `0003*.sql` filenames (rename if the tool requires a different scheme)
- [ ] `make migrate` target added that applies pending migrations
- [ ] `make migrate-status` (or equivalent) shows applied vs pending
- [ ] CI hook documented for staging/prod (don't have to wire CI yet; document it)
- [ ] `README.md` "Database" section updated to use the tool, not raw psql

## Files / surfaces

- `docs/decisions/0006-migration-tool.md` (new)
- `db/migrations/*` (possibly rename)
- `Makefile`
- `README.md`
- Tool-specific config file (e.g., `atlas.hcl`, `dbmate.yml`)

## Notes

Blocked by [[0002]] because the data-model decision determines whether
we keep the existing 3 migrations as-is or rewrite them. InsForge has
its own migration tooling — check `insforge-cli` skill before picking
an external tool.

## Log

## Outcome
