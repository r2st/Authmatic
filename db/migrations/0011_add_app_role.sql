-- Non-privileged application role for RLS enforcement (ticket 0034).
--
-- VERIFIED finding: RLS (0007) + FORCE RLS (0010) only enforce against a role
-- that is NOT a superuser and NOT the table owner and lacks BYPASSRLS. The
-- default `authmatic` role is a superuser, so it silently bypassed every
-- tenant_isolation policy. Tested against a real Postgres: as a non-superuser
-- role with `app.clinic_id` set, clinic B reading clinic A's patient returns 0
-- rows; the superuser returns 1.
--
-- User-driven queries (the tenant-scoped client, ticket 0034) MUST connect as
-- this role and `SET app.clinic_id = <session.clinic_id>` per request. The
-- admin/back-office client stays on the owner/superuser connection (it
-- legitimately spans tenants — seeds, audit writes, users lookup).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authmatic_app') THEN
    -- NOLOGIN here; ops grants LOGIN + a password from the secrets vault
    -- (ticket 0023) so no credential is committed in a migration.
    CREATE ROLE authmatic_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public, auth TO authmatic_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authmatic_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authmatic_app;
-- Future tables inherit the grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authmatic_app;

-- ACTION REQUIRED (ops): `ALTER ROLE authmatic_app LOGIN PASSWORD '<from vault>'`
-- and point the tenant-scoped client's connection string at it.
