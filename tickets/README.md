# Tickets

Lightweight, file-based coordination for multiple agents (human or AI)
working on Authmatic in parallel. Git is the audit log. No external tool
to set up.

## Layout

```
tickets/
├── _template.md       Copy this to start a new ticket.
├── inbox/             Unclaimed work. Open season.
├── active/            Claimed and in progress. Has an `owner`.
└── done/              Completed. Has an `outcome` summary at the bottom.
```

## Workflow

1. **Pick from `inbox/`.** Lowest-priority number first (P0 > P1 > P2 > P3),
   then lowest ID. Skip anything with unmet `depends_on`.
2. **Claim it.** `git mv tickets/inbox/NNNN-foo.md tickets/active/`. Edit
   frontmatter: set `owner`, `started`, `status: active`.
3. **Work the file as you go.** Tick acceptance-criteria checkboxes.
   Drop notes in `## Log` so the next agent can pick up cold.
4. **If blocked, set `status: blocked`** and add a `## Blocked on` section
   explaining what unblocks it. Leave it in `active/`.
5. **Done?** Tick all the boxes, add `## Outcome` (2–3 lines + commit
   hash or PR link), set `closed`, then
   `git mv tickets/active/NNNN-foo.md tickets/done/`.

## Creating a ticket

```bash
cp tickets/_template.md tickets/inbox/$(printf '%04d' $((1 + $(ls tickets/{inbox,active,done}/*.md 2>/dev/null | wc -l))))-short-slug.md
```

Fill in the frontmatter and the `## Goal` + `## Acceptance criteria`
sections. Everything else can wait.

## Rules

- **One active ticket per agent.** If you find yourself "while I'm here…",
  write a new ticket in `inbox/` instead.
- **List every file you'll touch** under `## Files / surfaces`. Other
  agents grep this to avoid collisions before they claim.
- **Never edit a `done/` ticket.** Open a follow-up in `inbox/` instead.
- **One PR per ticket** when possible. Reference the ticket ID in the PR
  title: `[T0007] add ICD-10 validator`.

## Areas

The `area` field is one of:

- `web` — `apps/web/`
- `agent` — `apps/agent/`
- `db` — `db/migrations/`, schema work
- `infra` — `infra/`, deploy configs, CI
- `docs` — `docs/`, ADRs, READMEs
- `shared` — `packages/shared/`
- `multi` — touches more than one of the above (call it out in the body)

## Production-readiness roadmap

Two audits (security/ops + correctness) produced 0005–0033. They cluster
into five tracks. Within a track, work top-to-bottom. Across tracks, the
P0s can proceed in parallel by different agents.

**1. Decide the agent (do this first — it unblocks the most)**
- `0025` reconcile the two agent implementations ← keystone
- then `0026` (remove theatrical pacing), `0014` (prompt injection),
  `0021` (tracing) all depend on which agent is canonical

**2. Make the clinical workflow real (P0 — patient safety)**
- `0029` process the uploaded document (stop replaying fixtures)
- `0030` adjudication safety (no default-approve, no keyword decisions)
- `0031` remove hardcoded identity (fake NPI) from submissions
- `0013` harden the upload (after 0029 makes it a live path)

**3. Make runs durable (P0/P1 — runs currently vanish)**
- `0027` durable job queue (stop fire-and-forget)
- `0028` durable run/SSE state (fix multi-instance double-filing)
- `0016` remove silent in-memory fallbacks
- `0017` idempotency keys (guards the double-file paths above)

**4. Lock down access (P0 — everything is currently open)**
- `0005` real auth + per-route authz
- `0006` clinic_id + RLS (depends 0005, 0002)
- `0007` unguessable reference IDs
- `0008` PHI handling policy + audit log
- `0018` adjudicate-patch allowlist (depends 0005)
- `0012` rate limiting · `0024` security headers

**5. Operability (P1/P2 — can't run blind in prod)**
- `0009` CI · `0010` tests · `0032` typecheck+lint
- `0011` logging+error reporting · `0021` tracing
- `0015` health/readiness · `0019` env separation+prod guards
- `0020` deploy manifests · `0033` pin deps
- `0022` backups/DR/runbook · `0023` secrets rotation · `0003` migration tool

A fresh agent with no context should claim **`0025`** or **`0005`** —
nothing downstream is safe to build until the agent is chosen and the
doors are locked.
