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

> **Status (2026-06-03 re-audit):** 27 tickets in `done/` (0001–0020,
> 0022–0024, 0030–0033) — verified by `tsc` clean, 39 passing tests, and
> route-wiring spot checks. The work is real and integrated. **But several
> "done" items are code-complete, not runtime-enforced** — see the two new
> follow-ups below. Remaining real work is the agent epic plus deploy
> verification.

### Open — what's actually left

**A. The agent epic (needs both services running to build/test)**
- `0025` make the Python agent canonical — **build phase** (decision done,
  ADR 0013). Keystone for the rest.
- `0029` process the uploaded document (stop replaying fixtures)
- `0027` durable job queue · `0028` durable run/SSE state
- `0026` remove theatrical pacing · `0021` distributed tracing
- `0014` prompt-injection mitigation
  (all depend on `0025`)

**B. Runtime enforcement / deploy verification (needs live InsForge)**
- `0034` **wire the tenant-scoped client so RLS actually enforces** — today
  `getInsForgeClient()` returns the admin client (RLS bypassed); isolation
  is app-layer-only. P0.
- `0035` apply + verify migrations 0004–0009 against staging/prod, then run
  the cross-tenant RLS test.

### Done (code-complete, verified offline)

Access/security: `0005` auth, `0006` RLS *(written; enforce via 0034)*,
`0007` ref-ids, `0008` PHI+audit, `0012` rate-limit, `0017` idempotency,
`0018` patch allowlist, `0024` headers, `0031` NPI/identity.
Correctness: `0016` no silent fallbacks, `0030` adjudication safety.
Ops: `0003` migration tool, `0009` CI, `0010` tests, `0011` logging,
`0013` upload hardening, `0015` health, `0019` env guards, `0020` deploy,
`0022` runbook, `0023` secrets, `0032` lint, `0033` deps.

A fresh agent should claim **`0034`** (close the RLS-bypass — highest
open security gap) or **`0025`** (the agent build phase). Everything in
group B needs InsForge credentials; group A needs `make dev` running both
services.
