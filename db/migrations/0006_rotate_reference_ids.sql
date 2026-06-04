-- Rotate sequential PA-2026-NNNNN reference ids to unguessable ids (ticket 0007).
-- One-shot: preserve the old id as legacy_reference_id (for in-flight customer
-- references), then overwrite reference_id with `PA-` + 16 hex chars of CSPRNG
-- entropy — the SAME format apps/web/src/lib/reference-id.ts generates.
--
-- pgcrypto (gen_random_bytes) is enabled by 0001_baseline.sql.

ALTER TABLE pa_submissions
  ADD COLUMN IF NOT EXISTS legacy_reference_id TEXT;

-- Keep the original id discoverable.
UPDATE pa_submissions
   SET legacy_reference_id = reference_id
 WHERE legacy_reference_id IS NULL
   AND reference_id LIKE 'PA-2026-%';

-- Rotate only the rows still on the old scheme. Loop guards against the
-- (astronomically unlikely) hex collision on the unique PK.
DO $$
DECLARE
  r        RECORD;
  new_id   TEXT;
BEGIN
  FOR r IN SELECT reference_id FROM pa_submissions WHERE reference_id LIKE 'PA-2026-%' LOOP
    LOOP
      new_id := 'PA-' || upper(encode(gen_random_bytes(8), 'hex'));
      EXIT WHEN NOT EXISTS (SELECT 1 FROM pa_submissions WHERE reference_id = new_id);
    END LOOP;
    UPDATE pa_submissions SET reference_id = new_id WHERE reference_id = r.reference_id;
  END LOOP;
END $$;

-- reference_id stays the PRIMARY KEY (unique index preserved from 0002).
-- Index legacy ids so support can still resolve an old reference.
CREATE INDEX IF NOT EXISTS pa_submissions_legacy_ref_idx
  ON pa_submissions (legacy_reference_id)
  WHERE legacy_reference_id IS NOT NULL;
