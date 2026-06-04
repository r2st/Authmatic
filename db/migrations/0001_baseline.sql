-- Authmatic — Insforge Postgres schema
-- Apply with: psql "$INSFORGE_DB_URL" -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- pgvector is optional. Available on the local docker (pgvector/pgvector
-- image) but not on Insforge cloud. Skip silently when it's missing —
-- pa_embeddings (below) is then also skipped, and the SQL-keyed RAG path
-- in apps/agent/src/persist.py runs without it.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS "vector";
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pgvector not available, skipping (% — %)', SQLSTATE, SQLERRM;
END $$;

-- ─── patients ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name   TEXT NOT NULL,
  dob         DATE NOT NULL,
  plan_id     TEXT NOT NULL,                       -- e.g. "UHC-CHOICE-PLUS"
  member_id   TEXT NOT NULL UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── prior_auths ─────────────────────────────────────────────────────
-- One row per agent run. The "run_id" the UI uses == prior_auths.id.
CREATE TABLE IF NOT EXISTS prior_auths (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id      UUID NOT NULL REFERENCES patients(id),
  drug_name       TEXT NOT NULL,
  drug_ndc        TEXT,
  dose            TEXT,
  diagnosis_code  TEXT,                            -- ICD-10
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','submitted','approved','denied','error')),
  receipt_url     TEXT,                            -- payer confirmation URL
  trigger_pdf_key TEXT,                            -- Insforge storage key
  rationale       TEXT,                            -- medical necessity letter
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS prior_auths_status_idx ON prior_auths(status);
CREATE INDEX IF NOT EXISTS prior_auths_patient_idx ON prior_auths(patient_id);

-- ─── agent_events ────────────────────────────────────────────────────
-- One row per ReAct iteration. Powers /run/:id audit trail.
CREATE TABLE IF NOT EXISTS agent_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id        UUID NOT NULL REFERENCES prior_auths(id) ON DELETE CASCADE,
  step_no      INT NOT NULL,
  verb         TEXT NOT NULL
               CHECK (verb IN ('READ-WEB','EXECUTE','VERIFY','PERSIST','ACTION')),
  plan         TEXT,                               -- planner's plan for this step
  tool_input   JSONB,
  tool_output  JSONB,
  duration_ms  INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (pa_id, step_no)
);

CREATE INDEX IF NOT EXISTS agent_events_pa_idx ON agent_events(pa_id, step_no);

-- ─── pa_embeddings ───────────────────────────────────────────────────
-- pgvector RAG over past approved rationales. Conditional on the vector
-- extension being available. The SQL-keyed RAG in persist.py works
-- without this table; the embeddings path is for the live-mode upgrade.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    CREATE TABLE IF NOT EXISTS pa_embeddings (
      id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      pa_id        UUID NOT NULL REFERENCES prior_auths(id) ON DELETE CASCADE,
      rationale    TEXT NOT NULL,
      embedding    VECTOR(1536) NOT NULL,
      created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS pa_embeddings_vec_idx
      ON pa_embeddings USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
  ELSE
    RAISE NOTICE 'skipping pa_embeddings table (vector extension not installed)';
  END IF;
END $$;

-- ─── compliance_scans ────────────────────────────────────────────────
-- Opsera VERIFY results — one per PA.
CREATE TABLE IF NOT EXISTS compliance_scans (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id          UUID NOT NULL REFERENCES prior_auths(id) ON DELETE CASCADE,
  passed         BOOLEAN NOT NULL,
  flagged_fields JSONB,
  raw_response   JSONB,
  scanned_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS compliance_scans_pa_idx ON compliance_scans(pa_id);

-- ─── updated_at trigger ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prior_auths_updated_at ON prior_auths;
CREATE TRIGGER prior_auths_updated_at
  BEFORE UPDATE ON prior_auths
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
