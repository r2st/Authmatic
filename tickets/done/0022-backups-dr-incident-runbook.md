---
id: 0022
title: Backups, DR plan, and incident-response runbook
area: docs
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

There is no documented backup procedure, no recovery test, no on-call
runbook. For a HIPAA-regulated product, "we lost the database" is a
breach.

## Acceptance criteria

- [x] `docs/runbook.md` — severity table, escalation tree, playbooks (readyz/InsForge down, stuck run, prompt injection, sponsor outage), comms cadence.
- [x] `docs/backups.md` — InsForge managed + supplemental `pg_dump`, Tigris versioning + 90-day lifecycle, least-priv access + two-person restore.
- [~] Quarterly restore drill — cadence + procedure defined; **first drill ACTION REQUIRED** (needs a live scratch project) — flagged, not faked.
- [x] RPO ≤ 1h / RTO ≤ 4h stated + justified (ADR 0011).
- [x] HIPAA breach procedure (§164.404–410) + notification template + Privacy-Officer-decides log (ADR 0011 + runbook §6).
- [x] On-call tool picked: **PagerDuty** (ADR 0011, with rationale).
- [x] `docs/decisions/0011-backup-dr-strategy.md` records the choices + ACTION REQUIRED items.

## Files / surfaces

- `docs/runbook.md` (new)
- `docs/backups.md` (new)
- `docs/decisions/0011-backup-dr-strategy.md` (new)

## Notes

This ticket is mostly writing + verifying — but the writing forces the
team to confront what we'd actually do at 3 AM. A draft is better
than nothing; iterate over time.

## Log

- 2026-06-03 (claude): Drafted docs/runbook.md + docs/backups.md (RPO/RTO, HIPAA breach steps). REMAINING: schedule + record first restore drill, pick on-call tool, write ADR 0011.

## Outcome

## Log

- 2026-06-03 — Taken over from a stalled session that drafted runbook.md
  + backups.md (both solid). Wrote the missing ADR 0011 recording the
  choices: backup mechanism, RPO ≤ 1h / RTO ≤ 4h with justification,
  PagerDuty as the on-call tool, restore-drill cadence, and a HIPAA
  breach-notice template + Privacy-Officer decision ownership.
- ACTION REQUIRED (human): stand up PagerDuty; run + record the first
  quarterly restore drill; confirm InsForge backup retention/encryption
  in the BAA; appoint the Privacy Officer.

## Outcome

Backup, DR, and incident response are documented: runbook (severity,
escalation, playbooks), backups (mechanism, lifecycle, access), and ADR
0011 (RPO/RTO, PagerDuty, breach template + decision log). Remaining
items are operational/legal ACTION REQUIRED, flagged honestly.
