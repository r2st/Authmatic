-- Durable job queue for agent runs (ticket 0027). Replaces fire-and-forget
-- `asyncio.create_task` / `void runAgentPipeline` — which silently drop work
-- when a serverless/autoscaled instance is frozen or killed mid-run.
--
-- A worker (apps/agent/src/worker.py) claims jobs with
-- `FOR UPDATE SKIP LOCKED`, runs the agent, and marks them done/failed with
-- bounded retries + dead-lettering. At-least-once; idempotency (ticket 0017 +
-- the UNIQUE run_id here) prevents double-filing.

CREATE TABLE IF NOT EXISTS jobs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id       UUID NOT NULL UNIQUE REFERENCES prior_auths(id) ON DELETE CASCADE,
  clinic_id    UUID,                         -- denormalized for worker context
  kind         TEXT NOT NULL DEFAULT 'agent_run',
  -- The uploaded PDF travels with the job so the worker is self-contained and
  -- the run survives an API-instance restart. Transient PHI: cleared when the
  -- job reaches a terminal state (worker nulls pdf_bytes on done/dead).
  pdf_bytes    BYTEA,
  filename     TEXT,
  status       TEXT NOT NULL DEFAULT 'queued'
               CHECK (status IN ('queued','running','done','failed','dead')),
  attempts     INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  last_error   TEXT,
  locked_at    TIMESTAMPTZ,                  -- set when a worker claims it; stuck-run detection
  locked_by    TEXT,                         -- worker id, for debugging
  run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),  -- backoff: don't retry before this
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Worker claim query filters on (status, run_after); index it.
CREATE INDEX IF NOT EXISTS jobs_claimable_idx ON jobs (status, run_after)
  WHERE status IN ('queued','running');
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status);

DROP TRIGGER IF EXISTS jobs_updated_at ON jobs;
CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
