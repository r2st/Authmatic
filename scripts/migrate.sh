#!/usr/bin/env bash
# scripts/migrate.sh — apply / list db/migrations against $INSFORGE_DB_URL.
#
# A dependency-free forward migration runner (ticket 0003, ADR 0006). Tracks
# applied migrations in a schema_migrations table; applies pending ones in
# filename order, each inside a transaction. Works with the existing plain
# `db/migrations/NNNN_*.sql` files unchanged (no markers, no rename) and needs
# only `psql` — the same tool InsForge Postgres already speaks.
#
# Usage:
#   scripts/migrate.sh up       # apply all pending migrations (default)
#   scripts/migrate.sh status   # show applied vs pending

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then set -a; source .env; set +a; fi
: "${INSFORGE_DB_URL:?INSFORGE_DB_URL must be set}"

MIGRATIONS_DIR="db/migrations"
CMD="${1:-up}"

ensure_table() {
  psql "$INSFORGE_DB_URL" -v ON_ERROR_STOP=1 -q -c "
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version    TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );" >/dev/null
}

applied_versions() {
  psql "$INSFORGE_DB_URL" -t -A -c "SELECT version FROM schema_migrations ORDER BY version;"
}

is_applied() {
  local v="$1"
  psql "$INSFORGE_DB_URL" -t -A -c \
    "SELECT 1 FROM schema_migrations WHERE version = '$v';" | grep -q 1
}

cmd_status() {
  ensure_table
  echo "Migration status (applied ✔ / pending ✗):"
  for f in "$MIGRATIONS_DIR"/*.sql; do
    v="$(basename "$f" .sql)"
    if is_applied "$v"; then echo "  ✔ $v"; else echo "  ✗ $v"; fi
  done
}

cmd_up() {
  ensure_table
  local applied=0
  for f in "$MIGRATIONS_DIR"/*.sql; do
    v="$(basename "$f" .sql)"
    if is_applied "$v"; then continue; fi
    echo "→ applying $v"
    # Each migration + its bookkeeping commit atomically.
    psql "$INSFORGE_DB_URL" -v ON_ERROR_STOP=1 --single-transaction -q \
      -f "$f" \
      -c "INSERT INTO schema_migrations (version) VALUES ('$v');"
    applied=$((applied + 1))
  done
  if [[ $applied -eq 0 ]]; then echo "Already up to date."; else echo "Applied $applied migration(s)."; fi
}

case "$CMD" in
  up)     cmd_up ;;
  status) cmd_status ;;
  *) echo "usage: scripts/migrate.sh [up|status]" >&2; exit 2 ;;
esac
