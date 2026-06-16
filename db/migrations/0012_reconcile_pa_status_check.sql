-- Reconcile pa_submissions.status CHECK with the app's PaStatus enum.
--
-- Found during browser testing: the original CHECK (migration 0002/0003)
-- allows {pending_review, approved, denied, submitted}, but the application's
-- PaStatus type + the adjudication state machine (submissions.ts
-- ALLOWED_TRANSITIONS) use `under_review` and `needs_info`. Advancing a PA to
-- "Medical Review" (pending_review → under_review) therefore violated the DB
-- constraint. This widens the CHECK to the full PaStatus set (keeping the
-- legacy `submitted` value so any pre-existing row stays valid).

ALTER TABLE pa_submissions DROP CONSTRAINT IF EXISTS pa_submissions_status_check;
ALTER TABLE pa_submissions
  ADD CONSTRAINT pa_submissions_status_check
  CHECK (status IN (
    'pending_review',
    'under_review',
    'needs_info',
    'approved',
    'denied',
    'submitted'   -- legacy (agent path); kept for back-compat
  ));
