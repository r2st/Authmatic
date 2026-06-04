-- Audit log — who read or mutated which PHI resource, when.
-- Required by ADR 0008 (PHI handling policy) and HIPAA Security Rule
-- §164.312(b). Write one row on every getSubmission / getRun, every
-- adjudication, and every cross-clinic access attempt (allowed=false).
--
-- Spans both data-model subdomains (ADR 0005) deliberately — it is the one
-- table that observes the whole system. `clinic_id` is added by the
-- multi-tenant migration (ticket 0006); until then it is nullable.

CREATE TABLE IF NOT EXISTS audit_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_id     TEXT,                       -- session user id / email; null = system/agent
  actor_clinic TEXT,                       -- caller's clinic (for cross-tenant detection)
  action       TEXT NOT NULL
               CHECK (action IN ('read','create','update','delete','adjudicate','login','access_denied')),
  resource     TEXT NOT NULL,              -- e.g. 'pa_submission', 'prior_auth', 'run'
  resource_id  TEXT,                       -- reference_id / run_id / pa_id
  allowed      BOOLEAN NOT NULL DEFAULT true,
  detail       JSONB                       -- redacted context only; NEVER raw PHI (ADR 0008)
);

CREATE INDEX IF NOT EXISTS audit_log_at_idx        ON audit_log (at DESC);
CREATE INDEX IF NOT EXISTS audit_log_resource_idx  ON audit_log (resource, resource_id);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx     ON audit_log (actor_id);
-- Cross-tenant access attempts are the highest-signal security events.
CREATE INDEX IF NOT EXISTS audit_log_denied_idx    ON audit_log (at DESC) WHERE allowed = false;
