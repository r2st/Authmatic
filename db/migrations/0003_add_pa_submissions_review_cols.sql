-- Add the adjudication-trail columns the TS DbRow type expects on
-- pa_submissions (see apps/web/src/lib/submissions.ts DbRow + rowToSubmission).
-- Without these, SELECT * still works (rows come back without the field),
-- but the in-memory fallback can't model status transitions cleanly.

ALTER TABLE pa_submissions
  ADD COLUMN IF NOT EXISTS under_review_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS decided_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS decision_notes  TEXT,
  ADD COLUMN IF NOT EXISTS denial_reason   TEXT,
  ADD COLUMN IF NOT EXISTS reviewer_id     TEXT;
