-- Make RLS actually enforce (ticket 0034). `ENABLE ROW LEVEL SECURITY` (0007)
-- does NOT apply to the table OWNER — and the app connects as the owner role,
-- so the tenant_isolation policies were silently bypassed (verified: clinic B
-- could read clinic A's patient). `FORCE ROW LEVEL SECURITY` applies the
-- policies to the owner too, so `app.clinic_id` scoping is enforced for every
-- connection, not just non-owner roles.

DO $$
DECLARE t TEXT;
  tables TEXT[] := ARRAY[
    'patients','prior_auths','agent_events','pa_submissions',
    'compliance_scans','users','providers'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  END LOOP;
  IF to_regclass('public.pa_embeddings') IS NOT NULL THEN
    ALTER TABLE pa_embeddings FORCE ROW LEVEL SECURITY;
  END IF;
END $$;

-- NOTE: with FORCE RLS, every app query MUST run on a connection that has set
-- `app.clinic_id` (the tenant-scoped client, ticket 0034) — otherwise
-- auth.clinic_id() is NULL and the row is invisible. Back-office/admin tooling
-- uses a BYPASSRLS role or the dedicated admin connection. audit_log is left
-- un-forced on purpose (it records cross-tenant attempts; written by admin).
