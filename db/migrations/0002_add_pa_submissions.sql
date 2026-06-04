-- Add pa_submissions table for the clinic-UI / HealthFirst submission flow.
-- Referenced by apps/web/src/lib/submissions.ts:
--   - select reference_id (next-id lookup, sorted desc)
--   - insert(reference_id, patient/payer fields, status, submitted_at)
--   - select * / update(patch) for status transitions (pending_review -> approved/denied)

CREATE TABLE IF NOT EXISTS pa_submissions (
  reference_id   TEXT        PRIMARY KEY,
  patient_name   TEXT        NOT NULL,
  dob            TEXT        NOT NULL,
  member_id      TEXT        NOT NULL,
  diagnosis      TEXT        NOT NULL,
  medication     TEXT        NOT NULL,
  dosage         TEXT,
  provider_name  TEXT,
  justification  TEXT,
  status         TEXT        NOT NULL DEFAULT 'pending_review',
  submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  adjudication   JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status IN ('pending_review', 'approved', 'denied', 'submitted'))
);

CREATE INDEX IF NOT EXISTS pa_submissions_status_idx ON pa_submissions (status);
CREATE INDEX IF NOT EXISTS pa_submissions_submitted_at_idx ON pa_submissions (submitted_at DESC);
