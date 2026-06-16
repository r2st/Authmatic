---
id: 0036
title: Reconcile pa_submissions.status CHECK with the PaStatus enum
area: db
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

The `pa_submissions.status` CHECK constraint (migrations 0002/0003) allowed
only `{pending_review, approved, denied, submitted}`, but the application's
`PaStatus` type and the adjudication state machine
(`submissions.ts` ALLOWED_TRANSITIONS) use `under_review` and `needs_info`.
So advancing a PA to "Medical Review" (`pending_review → under_review`) hit a
DB constraint violation. Found during browser end-to-end testing.

## Acceptance criteria

- [x] Migration widens the CHECK to the full `PaStatus` set (`pending_review,
      under_review, needs_info, approved, denied`) + keeps legacy `submitted`.
- [x] `pending_review → under_review` and `→ needs_info` verified against a
      real Postgres.
- [x] Full adjudication flow works end-to-end through the app
      (`POST /api/pa/[ref]/adjudicate`): pending_review → under_review →
      approved, persisted durably.
- [x] Migration linter clean.

## Files / surfaces

- `db/migrations/0012_reconcile_pa_status_check.sql` (new)

## Log

- 2026-06-03 — Discovered during the browser test (the status timeline's
  "Medical Review" step would have 500'd on the under_review write). Added
  `0012_reconcile_pa_status_check.sql` (DROP + re-ADD the CHECK with the full
  set). Applied to the local Postgres; verified `under_review` + `needs_info`
  transitions, then ran a real adjudication via the app → `approved` (reviewer
  HF-MCR-8842), durable in `pa_submissions`. Browser status page renders
  Submitted → Pending Review → Medical Review → Approved. Linter clean (12
  migrations).

## Outcome

The DB status CHECK now matches the app's `PaStatus` enum, so the full PA
lifecycle (submit → review → decision) runs without constraint errors —
verified end-to-end in the browser against real Postgres.
