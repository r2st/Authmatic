# Project guide for agents

Authmatic is an autonomous agent that files prior authorizations on real
payer portals. This file is the entry point for any AI agent or
contributor working in the repo — read it before doing anything.

## Repo layout

| You need…                             | Look in                                  |
|---------------------------------------|------------------------------------------|
| **What to work on next**              | `tickets/inbox/` (read `tickets/README.md` first) |
| Work in progress                      | `tickets/active/`                        |
| Completed work                        | `tickets/done/`                          |
| The web UI                            | `apps/web/`                              |
| The agent service (FastAPI)           | `apps/agent/`                            |
| Shared TS types                       | `packages/shared/`                       |
| SQL migrations                        | `db/migrations/`                         |
| HealthFirst portal + case fixtures    | `fixtures/`                              |
| Local Docker stack                    | `infra/docker-compose.local.yml`         |
| Seed / smoke / reset scripts          | `scripts/`                               |
| Architecture, spec, sponsor notes     | `docs/`                                  |
| Demo PDFs, sponsor fixtures           | `assets/`                                |
| Pitch script, recordings              | `demo/`                                  |
| Hackathon coordination history        | `../archive/` (frozen — do not edit)     |

## Working rules

1. **Claim before you build.** Pick a ticket from `tickets/inbox/`,
   `git mv` it to `tickets/active/`, set `owner` + `started`. Don't start
   work on something nobody owns. One active ticket per agent at a time.
2. **Update the ticket as you go.** It's the single source of truth for
   what's done and what's blocked. Other agents read the `## Log`
   section before claiming overlapping work.
3. **When done, `git mv` to `tickets/done/`** with an `## Outcome` summary
   (2–3 lines + commit hash or PR link).
4. **Don't edit `../archive/`.** It holds hackathon coordination history.
   New context goes in `docs/`.
5. **Big decisions get an ADR** in `docs/decisions/`. Anything another
   contributor might second-guess (framework choice, schema shape,
   sponsor API usage) is fair game. Reference the ADR from the ticket
   that drove it.
6. **One migration per change.** Add a new numbered file in
   `db/migrations/` — never edit an applied migration. The starting
   schema is `0001_baseline.sql`; everything since is incremental.
7. **Fixtures over secrets in tests.** Use `fixtures/healthfirst-*.json`
   for any test that needs payer data.

## Stack snapshot

- **Web:** Next.js 14 App Router, TypeScript, Tailwind, hosted on Render
- **Agent:** Python 3.12, FastAPI, SSE streaming, hosted on Render
- **Backend:** InsForge (Postgres + Storage + Auth + Edge Functions)
- **Browser automation:** Rtrvr.ai
- **Sandbox:** Daytona
- **Object storage:** Tigris (S3-compatible)
- **Compliance scanning:** Opsera

## InsForge backend

This project uses [InsForge](https://insforge.dev): a Postgres-based BaaS
that provides database, auth, storage, edge functions, realtime, an AI
model gateway, and payments.

- **Project:** **hackathon-31may2026**
- **API base:** `https://z739c3mi.us-east.insforge.app`
- **Credentials:** app code reads keys from `.env.local`; the CLI reads
  `.insforge/project.json`. Never hardcode or commit keys.

Use the installed InsForge skills before improvising:

- `insforge` — `@insforge/sdk` client (CRUD, auth, storage, functions, realtime, AI, email, Stripe)
- `insforge-cli` — backend infrastructure via the `insforge` CLI (projects, SQL, migrations, RLS, storage buckets, functions, secrets, schedules)
- `insforge-debug` — diagnosing failures (SDK/HTTP errors, RLS denials, auth/OAuth issues), security and performance audits
- `insforge-integrations` — wiring external auth providers (Clerk, Auth0, WorkOS, Better Auth) for JWT-based RLS

Key patterns:

- Database inserts take an array: `insert([{ ... }])`.
- Reference users with `auth.users(id)`; use `auth.uid()` in RLS policies.
- For storage uploads, persist both the returned `url` and `key`.

## Tone for human-facing artifacts

- Pitch and demo copy: confident, concrete, names a real customer & real pain.
- ADRs, docs, READMEs: terse. Bullet points beat paragraphs.
- No emojis unless the human asks for them.
