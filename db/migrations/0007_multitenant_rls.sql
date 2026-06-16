-- Multi-tenant isolation enforced by the database (ticket 0006).
-- Adds clinics, a clinic_id FK on every PHI table + users, enables RLS, and
-- creates per-table tenant-isolation policies. Builds on 0005 (users).
--
-- Tenancy key in the DB session: `app.clinic_id` GUC. The application sets it
-- per request on a scoped connection (`SET app.clinic_id = '<uuid>'`) or via an
-- InsForge JWT claim mapped to it. `auth.clinic_id()` reads it. Until the
-- scoped client is fully wired (see ADR 0007), app-layer ownership checks
-- (ticket 0005) remain the enforced control and RLS is defense-in-depth.

-- ─── clinics ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clinics (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Stable default clinic to backfill pre-existing rows onto.
INSERT INTO clinics (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default Clinic (backfill)')
ON CONFLICT (id) DO NOTHING;

-- ─── tenancy key accessor ────────────────────────────────────────────
-- Returns the caller's clinic from the per-session GUC, or NULL if unset
-- (admin/back-office connections leave it unset and bypass via the
-- BYPASSRLS role or the table-owner exemption).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.clinic_id() RETURNS uuid
  LANGUAGE sql STABLE
  AS $$ SELECT nullif(current_setting('app.clinic_id', true), '')::uuid $$;

-- ─── add clinic_id + backfill + NOT NULL + RLS, per table ────────────
DO $$
DECLARE
  t   TEXT;
  tables TEXT[] := ARRAY['patients','prior_auths','agent_events','pa_submissions','compliance_scans','users'];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id)', t);
    EXECUTE format('UPDATE %I SET clinic_id = ''00000000-0000-0000-0000-000000000001'' WHERE clinic_id IS NULL', t);
    EXECUTE format('ALTER TABLE %I ALTER COLUMN clinic_id SET NOT NULL', t);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (clinic_id)', t || '_clinic_idx', t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    -- Single policy covering select/update/delete + insert WITH CHECK.
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (clinic_id = auth.clinic_id()) WITH CHECK (clinic_id = auth.clinic_id())',
      t
    );
  END LOOP;
END $$;

-- pa_embeddings exists only when pgvector is installed (see 0001_baseline).
DO $$
BEGIN
  IF to_regclass('public.pa_embeddings') IS NOT NULL THEN
    ALTER TABLE pa_embeddings ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id);
    UPDATE pa_embeddings SET clinic_id = '00000000-0000-0000-0000-000000000001' WHERE clinic_id IS NULL;
    ALTER TABLE pa_embeddings ALTER COLUMN clinic_id SET NOT NULL;
    CREATE INDEX IF NOT EXISTS pa_embeddings_clinic_idx ON pa_embeddings (clinic_id);
    ALTER TABLE pa_embeddings ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON pa_embeddings;
    CREATE POLICY tenant_isolation ON pa_embeddings
      USING (clinic_id = auth.clinic_id()) WITH CHECK (clinic_id = auth.clinic_id());
  END IF;
END $$;

-- audit_log (0004) is intentionally NOT tenant-restricted by RLS: it must
-- record cross-tenant access *attempts*, so it is written by the
-- back-office/admin connection. It stores actor_clinic for filtering.
