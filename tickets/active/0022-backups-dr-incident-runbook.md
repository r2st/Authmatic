---
id: 0022
title: Backups, DR plan, and incident-response runbook
area: docs
priority: P2
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

There is no documented backup procedure, no recovery test, no on-call
runbook. For a HIPAA-regulated product, "we lost the database" is a
breach.

## Acceptance criteria

- [ ] `docs/runbook.md` — paging policy, severity definitions, escalation tree, common-incident playbooks (DB down, sponsor outage, prompt-injection detected)
- [ ] `docs/backups.md` — InsForge Postgres backup cadence (verify what InsForge provides; supplement with logical dumps if needed), Tigris bucket versioning + lifecycle rules, retention windows, where backups live, who can access
- [ ] Quarterly restore drill scheduled; first drill scheduled and outcome captured in this ticket's `## Log`
- [ ] RPO/RTO targets stated and justified (e.g., RPO ≤ 1 h, RTO ≤ 4 h)
- [ ] HIPAA breach-notification procedure documented per §164.404–410 (60-day window, notification template, log of who decides)
- [ ] On-call rotation tool picked (PagerDuty / Opsgenie / GitHub on-call)
- [ ] `docs/decisions/0011-backup-dr-strategy.md` records the choices

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
