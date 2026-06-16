---
id: 0002
title: ADR — unify or formally split the two data models
area: docs
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

Decide and document whether `patients` + `prior_auths` + `agent_events`
(agent-side, baseline schema) and `pa_submissions` (web-side, migrations
2–3) become one model or stay as two with a formal boundary.

Right now they are two disconnected tables serving overlapping purposes;
new contributors will get this wrong.

## Acceptance criteria

- [x] New ADR at `docs/decisions/0005-data-model-boundary.md`
- [x] ADR states: (a) current state, (b) chosen direction (unify | keep split | merge into one with named subdomains), (c) rationale, (d) consequences
- [x] N/A — direction is "keep split" (target schema sketch not needed)
- [x] "Keep split" — subdomain ownership map + optional `pa_submissions.agent_run_id` cross-link documented in ADR §d
- [x] ADR links to `apps/agent/src/persist.py` and `apps/web/src/lib/submissions.ts`
- [x] `docs/architecture.md` links to the new ADR above the `## Data model` SQL block

## Files / surfaces

- `docs/decisions/0005-data-model-boundary.md` (new)
- `docs/architecture.md`

## Notes

`db/migrations/0001_baseline.sql` has the agent-side model.
`db/migrations/0002_add_pa_submissions.sql` and `0003_*` add the
web-side. Neither references the other. The decision affects every
downstream ticket that touches persistence — write this before
[[0003]] or any data migration ticket.

## Log

- 2026-06-03 — Read both consumers and all three migrations. The two
  surfaces model different things: `prior_auths` is the audit-first
  agent-run record (UUID PK, FK to `patients`, `agent_events` timeline);
  `pa_submissions` is the denormalized clinic-form row (human-visible
  `PA-2026-NNNNN` PK, no FK, review-trail columns). Unifying would force
  one or the other to regress. Chose "keep split" with named subdomains
  and a documented optional cross-link.

## Outcome

ADR 0005 written and linked from `docs/architecture.md`. Direction is
"keep split": `agent_run` subdomain owns the baseline tables;
`clinic_form` subdomain owns `pa_submissions`. Cross-link
(`pa_submissions.agent_run_id`) is documented as a future option, not
implemented. Ticket 0004 can proceed against the web-side `PASubmission`
type only.
