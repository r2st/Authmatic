# Backups & disaster recovery

> Draft (ticket 0022). For a PHI product, "we lost the database" is a
> reportable event. Verify these against what InsForge actually provides.

## What to back up

| Store | Contents | Mechanism | Cadence |
|-------|----------|-----------|---------|
| InsForge Postgres | patients, prior_auths, agent_events, pa_submissions, audit log | InsForge managed backups (verify retention) + supplemental `pg_dump` to encrypted object storage | daily; supplemental dump nightly |
| Tigris bucket | chart/Rx PDFs, receipts | Bucket versioning + lifecycle | versioning on; 90-day noncurrent expiry |

## Targets

- **RPO ≤ 1 hour** — at most 1h of submissions lost in a disaster.
- **RTO ≤ 4 hours** — service restored within 4h.

## Restore drill

- Quarterly: restore the latest dump into a scratch project, run
  `make smoke`, confirm row counts. Record the result + date here.
- First drill: **TODO — schedule and capture outcome.**

## HIPAA breach notification

If PHI is lost or exposed:
1. Notify the privacy officer immediately (see [runbook.md](runbook.md)).
2. Breach assessment per HIPAA §164.402.
3. Notify affected individuals within **60 days** (§164.404); HHS and
   possibly media per thresholds (§164.408/410).
4. Document the timeline, scope, and remediation.

## Access

- Backup storage is least-privilege; access is logged and reviewed.
- Restore requires two-person approval in production.
