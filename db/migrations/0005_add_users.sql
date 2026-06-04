-- Real users for clinic sign-in (ticket 0005). Replaces the hardcoded
-- DEMO_USERS constant + localStorage sessions.
--
-- Passwords are scrypt hashes (apps/web/src/lib/auth/password.ts) in the
-- self-describing `scrypt$N$r$p$salt$hash` format — never plaintext.
-- `clinic_id` (FK -> clinics) is added by the multi-tenant migration
-- (ticket 0006); `clinic` (display name) is the tenant key until then.

CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT NOT NULL UNIQUE,         -- stored lowercased
  name          TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'MA'
                CHECK (role IN ('MA','Admin','Provider')),
  clinic        TEXT NOT NULL,                -- tenant key (pre-0006)
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS users_clinic_idx ON users (clinic);

DROP TRIGGER IF EXISTS users_updated_at ON users;
CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
