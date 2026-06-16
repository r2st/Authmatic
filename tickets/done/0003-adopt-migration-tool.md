---
id: 0003
title: Adopt a real migration tool for db/migrations/
area: db
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0002]
---

## Goal

Replace "run psql by hand" with a tool that tracks which migrations have
been applied to which environment. Picking a tool now, before the schema
grows further, prevents drift between dev/staging/prod.

## Acceptance criteria

- [x] ADR `docs/decisions/0006-migration-tool.md` — picked a dependency-free psql runner over golang-migrate/dbmate/Atlas/Prisma/InsForge-CLI, with the rationale (avoids editing 8 already-applied migrations + no new binary). Options table included.
- [x] Runs the existing `0001*.sql … 0008*.sql` filenames UNCHANGED (no rename, no markers) — version id = filename stem; tracked in `schema_migrations`.
- [x] `make migrate` → `scripts/migrate.sh up` (applies pending, transactional, idempotent).
- [x] `make migrate-status` → applied ✔ / pending ✗ listing.
- [x] CI hook documented (ADR 0006 + README): deploy job runs `make migrate` before app start; cross-ref to [[0009]] and [[0019]] prod guards.
- [x] README "Database" section rewritten to use `make migrate` / `make migrate-status`, not raw per-file psql.

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

## Log

- 2026-06-03 — Chose a minimal `psql`-based runner (`scripts/migrate.sh`,
  `bash -n` clean) + `make migrate`/`make migrate-status`, ADR 0006,
  README rewrite. Rationale: golang-migrate/dbmate/Atlas would force
  edits to the 8 already-applied migrations (rule 6 violation) or add an
  unpinnable binary; the runner uses the existing plain .sql files as-is
  and needs only psql, which InsForge already speaks.
- Could not execute against a live DB from here (no DB credentials/
  connection in this env) — syntax verified; the runner is transactional
  + idempotent by construction.

## Outcome

`db/migrations/` is now applied by a tracked, transactional runner
(`make migrate` / `make migrate-status`) instead of hand-run psql, with
a `schema_migrations` ledger. ADR 0006 records the choice; README + CI
hook documented. Existing migrations unchanged.
