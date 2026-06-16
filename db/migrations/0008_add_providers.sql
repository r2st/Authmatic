-- Prescriber/provider records (ticket 0031). The submission path must pull
-- prescriber identity (name + NPI) from verified records, never from a
-- literal. Linked to a clinic (ticket 0006 tenancy) and RLS-scoped.

CREATE TABLE IF NOT EXISTS providers (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id   UUID NOT NULL REFERENCES clinics(id),
  first_name  TEXT NOT NULL,
  last_name   TEXT NOT NULL,
  npi         TEXT NOT NULL,                 -- 10 digits, Luhn-validated in app
  taxonomy    TEXT,                          -- provider taxonomy code (specialty)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT providers_npi_format CHECK (npi ~ '^[0-9]{10}$'),
  UNIQUE (clinic_id, npi)
);

CREATE INDEX IF NOT EXISTS providers_clinic_idx ON providers (clinic_id);

ALTER TABLE providers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON providers;
CREATE POLICY tenant_isolation ON providers
  USING (clinic_id = auth.clinic_id())
  WITH CHECK (clinic_id = auth.clinic_id());
