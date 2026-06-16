-- Add payer integration columns to prior_auths for real ePA tracking.
--
-- external_reference_id: the payer/CoverMyMeds ID returned on submission.
-- payer_status: canonical status from the payer (separate from our internal
--   workflow status so we can reconcile divergences).
-- last_polled_at / next_poll_at: poller schedule bookkeeping.
-- poll_count: how many times we've polled (drives exponential backoff).
-- denial_reason: free-text from the payer explaining a denial.
-- appeal_count: how many appeals have been filed for this PA.

ALTER TABLE prior_auths
  ADD COLUMN IF NOT EXISTS external_reference_id TEXT,
  ADD COLUMN IF NOT EXISTS payer_status          TEXT,
  ADD COLUMN IF NOT EXISTS last_polled_at        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS next_poll_at          TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS poll_count            INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS denial_reason         TEXT,
  ADD COLUMN IF NOT EXISTS appeal_count          INTEGER DEFAULT 0;

-- Index for the poller query: "next_poll_at <= now() AND status not terminal".
CREATE INDEX IF NOT EXISTS prior_auths_poll_due_idx
  ON prior_auths (next_poll_at)
  WHERE payer_status NOT IN ('approved', 'denied', 'cancelled')
    AND next_poll_at IS NOT NULL;

-- Look up by payer's reference (e.g. webhook callbacks).
CREATE UNIQUE INDEX IF NOT EXISTS prior_auths_ext_ref_idx
  ON prior_auths (external_reference_id)
  WHERE external_reference_id IS NOT NULL;

-- Same columns on pa_submissions (the clinic-side table) for consistency.
ALTER TABLE pa_submissions
  ADD COLUMN IF NOT EXISTS external_reference_id TEXT,
  ADD COLUMN IF NOT EXISTS payer_status          TEXT,
  ADD COLUMN IF NOT EXISTS last_polled_at        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS next_poll_at          TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS poll_count            INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS appeal_count          INTEGER DEFAULT 0;
-- denial_reason already exists on pa_submissions (migration 0003).

CREATE INDEX IF NOT EXISTS pa_submissions_poll_due_idx
  ON pa_submissions (next_poll_at)
  WHERE payer_status NOT IN ('approved', 'denied', 'cancelled')
    AND next_poll_at IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS pa_submissions_ext_ref_idx
  ON pa_submissions (external_reference_id)
  WHERE external_reference_id IS NOT NULL;
