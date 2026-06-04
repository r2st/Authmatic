# ADR 0011 — Backup, DR, and incident strategy

- **Status:** accepted (procedures defined; several steps are human ACTION REQUIRED)
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0022-backups-dr-incident-runbook.md
- **Related:** [docs/runbook.md](../runbook.md), [docs/backups.md](../backups.md), [ADR 0008 PHI](0008-phi-handling-policy.md)

## Context

A HIPAA-regulated product with no documented backups, no recovery test, and
no on-call runbook: "we lost the database" is a reportable breach and an
unbounded outage. This ADR records the choices; the runbook + backups docs
are the operational detail.

## Decisions

**Backups.** InsForge-managed Postgres backups (verify retention in the BAA)
*plus* a nightly supplemental `pg_dump` to encrypted object storage — so
recovery never depends on a single provider. Tigris: bucket versioning on +
90-day noncurrent-version expiry.

**RPO / RTO.** RPO ≤ 1h (≤1h of submissions lost), RTO ≤ 4h (service back in
4h). Justification: PA filing is time-sensitive but not life-critical at the
second granularity; a 1h/4h target is achievable with nightly dumps +
managed backups without the cost of continuous replication. Revisit if
volume or SLAs grow.

**On-call tool.** **PagerDuty** (chosen over Opsgenie / GitHub on-call):
mature escalation policies, schedule overrides, and incident timelines that
double as the breach-decision record. Smaller teams could start with GitHub
on-call, but PagerDuty's escalation + audit trail is worth it for a
regulated product.

**Restore drills.** Quarterly: restore the latest dump into a scratch
project, run `make smoke`, confirm row counts; record date + outcome in the
0022 ticket Log. First drill: ACTION REQUIRED.

**Breach decision + notification.** The Privacy Officer (HIPAA-required role)
owns the breach determination. Procedure + 60-day timeline are in
runbook.md §6 / backups.md. Decisions (who decided, when, rationale, 4-factor
assessment) are logged in the incident record.

### Breach-notice template (fill per incident)

```
To: <affected individual>
Date of discovery: <date>   Date of breach: <date or "unknown">
What happened: <plain-language description>
PHI involved: <fields>
What we are doing: <containment + remediation>
What you can do: <steps>
Contact: <Privacy Officer name + phone>
```

## ACTION REQUIRED (human)

- Stand up the PagerDuty account + rotation + escalation policy.
- Schedule the first quarterly restore drill; capture the outcome.
- Confirm InsForge backup retention + encryption in the signed BAA.
- Appoint the Privacy Officer; store the breach-notice template in
  `docs/templates/`.

## Consequences

- Recovery no longer depends on one provider; targets are explicit.
- The incident runbook (severity, escalation, playbooks) + this ADR give
  on-call a starting point instead of tribal knowledge.
- Several items are process/infra (PagerDuty, drills, BAA) — tracked as
  ACTION REQUIRED, not silently closed.
