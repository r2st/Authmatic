# Contributing

## CI gates (ticket 0009)

`.github/workflows/ci.yml` runs on every PR and push to `main`:

| Job | Checks |
|---|---|
| `web` | `pnpm install --frozen-lockfile` → typecheck → lint → test (vitest) → build → `pnpm audit --prod` (non-blocking) |
| `agent` | install `requirements.txt` + `.[dev]` → `ruff check` → `mypy src` (baseline, non-blocking) → `pytest` → `pip-audit` (non-blocking) |
| `migrations` | `scripts/lint-migrations.sh` — rejects `DROP … ` without `IF EXISTS`, `TRUNCATE`, `DELETE` without `WHERE` |
| `secret-scan` | gitleaks over full history |

Dependency audits are **non-blocking** today (cleanup in progress, ticket
0033); flip to blocking once advisories are at zero. `mypy` is a lenient
baseline (ticket 0032); promote off `|| true` as type coverage grows.

## Branch protection (configure in GitHub repo settings)

`main` should require, before merge:

- All CI jobs green (`web`, `agent`, `migrations`, `secret-scan`).
- **1 approving review.**
- Branch up to date with `main`.
- No force-push, no deletion.

**ACTION REQUIRED (human):** these are GitHub repo settings, not in-repo
config — set them under Settings → Branches → Branch protection rules for
`main`. (Optionally encode via the `repository-rulesets` API later.)

## Local equivalents

```bash
make lint        # eslint (web) + ruff (agent)
make typecheck   # tsc --noEmit (web) + mypy src (agent)
pnpm --filter authmatic-web test
cd apps/agent && pytest -q
make migrate-status   # check schema drift before a DB-touching PR
```

## Working rules

See `tickets/README.md` for the file-based ticket workflow (claim → work →
move to `done/` with an `## Outcome`). One PR per ticket where possible;
reference the ticket id in the title (e.g. `[T0009] add CI pipeline`).
