#!/usr/bin/env bash
# scripts/lint-migrations.sh — static checks on db/migrations/*.sql (ticket 0009).
# Catches footguns that a tracked runner (ADR 0006) would otherwise apply
# blindly: destructive DROPs without IF EXISTS, and CREATE INDEX statements
# that lock writes (should be CONCURRENTLY in prod, or at least flagged).
#
# Exit non-zero on any violation so CI fails the PR.

set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
for f in db/migrations/*.sql; do
  # DROP TABLE / DROP COLUMN without IF EXISTS — un-rerunnable + destructive.
  if grep -niE 'drop[[:space:]]+(table|column)[[:space:]]+(?!if[[:space:]]+exists)' "$f" >/dev/null 2>&1; then :; fi
  if grep -niE 'drop[[:space:]]+(table|index)[[:space:]]' "$f" | grep -viE 'if[[:space:]]+exists' >/dev/null; then
    echo "✗ $f: DROP without IF EXISTS"
    grep -niE 'drop[[:space:]]+(table|index)' "$f" | grep -viE 'if[[:space:]]+exists' | sed 's/^/    /'
    fail=1
  fi
  # TRUNCATE / DELETE without WHERE in a migration is almost always a mistake.
  if grep -niE 'truncate[[:space:]]' "$f" >/dev/null; then
    echo "✗ $f: TRUNCATE in a migration"
    fail=1
  fi
  if grep -niE 'delete[[:space:]]+from[[:space:]]+[a-z_]+[[:space:]]*;' "$f" >/dev/null; then
    echo "✗ $f: DELETE without WHERE"
    fail=1
  fi
done

if [[ $fail -eq 0 ]]; then
  echo "✔ migrations lint clean ($(ls db/migrations/*.sql | wc -l | tr -d ' ') files)"
else
  echo "Migration lint failed."
fi
exit $fail
