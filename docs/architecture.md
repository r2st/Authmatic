# Authmatic — Architecture

> System design for the healthcare prior-authorization agent loop.

## System diagram

```
                ┌───────────────────────────────────────────────┐
                │  Browser UI (Next.js, Vercel / Render)        │
                │  ─ Dropzone (PDF)                             │
                │  ─ Live run stream (SSE)                      │
                │  ─ /run/:id auditor page  ◀── money shot      │
                └────────────────────┬──────────────────────────┘
                                     │ HTTP / SSE
                                     ▼
                ┌───────────────────────────────────────────────┐
                │  Agent service (Python / FastAPI on Render)   │
                │  ─ /api/run        (POST PDF → run_id)        │
                │  ─ /api/run/:id    (GET state)                │
                │  ─ /api/stream/:id (SSE: agent events)        │
                │                                               │
                │   ┌─────────────────────────────────────┐     │
                │   │  ReAct loop (≤5 iter)               │     │
                │   │  ─ Insforge model gateway           │     │
                │   │  ─ Picks one of 4 verbs per step    │     │
                │   └─────────────────────────────────────┘     │
                └────┬──────────┬─────────────┬───────────┬─────┘
                     │          │             │           │
                READ-WEB    EXECUTE        VERIFY      PERSIST
                     │          │             │           │
                     ▼          ▼             ▼           ▼
              ┌─────────┐ ┌─────────┐ ┌──────────────┐ ┌───────────────────┐
              │ Rtrvr   │ │ Daytona │ │ Opsera MCP   │ │ Insforge          │
              │ /agent  │ │ sandbox │ │ /mcp         │ │ Postgres+pgvector │
              │         │ │         │ │              │ │ + Storage         │
              │ UHC/    │ │ pdf →   │ │ PHI exposure │ │ + Edge functions  │
              │ Aetna/  │ │ ICD10 + │ │ scan on      │ │ + Model gateway   │
              │ CMM     │ │ dose    │ │ outgoing     │ │                   │
              │ portal  │ │ normal. │ │ packet       │ │                   │
              └────┬────┘ └─────────┘ └──────────────┘ └───────────────────┘
                   │
                   │  ACTION at end of loop:
                   │  Rtrvr fills + submits the form →
                   │  receipt URL pinned to /run/:id
                   ▼
              ┌─────────────────────────────┐
              │ Real (sandbox) payer page   │
              │ — judge clicks here at      │
              │   the end of the pitch.     │
              └─────────────────────────────┘
```

## Components

| Component | Owner role | Tech | Purpose |
|-----------|-----------|------|---------|
| Browser UI | Builder | Next.js + Tailwind | Dropzone, live stream, audit page |
| Agent service | Architect | Python 3.12 + FastAPI | The 4-verb ReAct loop, exposed via REST + SSE |
| Postgres + pgvector | Architect | Insforge | Cases, patients, prior approvals, audit log |
| Storage | Architect | Insforge (or Tigris stretch) | Prescription PDFs, insurance cards, form screenshots |
| Edge functions | Architect | Insforge Deno | Notification (Slack/SMS to doctor), receipt webhook |
| Sandbox runner | Architect | Daytona SDK | Executes pdfplumber + ICD-10 normalization |
| Browser agent | Architect | Rtrvr.ai REST | Drives the live payer portal |
| Compliance scan | Architect | Opsera MCP | PHI exposure + SQL/PII scan before persist |

## Agent loop (domain-specific)

The agent follows a bounded case-worker loop:

### 1. Trigger
- User uploads a **prescription PDF** through the dropzone.
- (Stretch) Brain2 webhook from a clinician voice note.

### 2. Context (Insforge)
| Surface | Holds |
|---------|-------|
| Postgres `patients` | Demographics, plan ID, prior diagnoses |
| Postgres `prior_auths` | Open + closed PAs for this patient |
| pgvector `pa_embeddings` | Embeddings of past approved rationales — RAG source |
| Storage `charts/` | The PDF the user just dropped |
| Rtrvr fetch | The current UHC coverage rule for `(drug, plan)` — re-fetched per run because rules drift weekly |

### 3. Tools (the 4 verbs)

| Verb | Sponsor | Invoke when |
|------|---------|-------------|
| READ-WEB | Rtrvr.ai | Fetch live coverage criteria from payer portal; submit final form |
| EXECUTE | Daytona | Parse PDF; normalize ICD-10 + dose; render the form payload |
| VERIFY | Opsera | Scan outgoing packet for PHI fields beyond what the form asks for |
| PERSIST | Insforge | DB writes; pgvector upsert; edge fn fires doctor notification |

### 4. Decision
- **Planner model:** Llama-3.1-70B (Insforge model gateway).
- **Pattern:** ReAct, **hard cap ≤5 iterations**.
- **Escalation:** If after 5 iterations the form isn't ready,
  agent writes "needs human review" + a Slack ping; the demo flow
  never hits this path, but Q&A loves to ask.

### 5. Action
- **FILE.** Rtrvr clicks submit on the payer portal in a cloud browser
  session. Returns a confirmation URL (the receipt).
- The receipt URL is written back to `prior_auths.receipt_url` and
  becomes the pinned link on `/run/:id`.

### 6. Artifact (the money shot)
- `/run/:id` — server-rendered page with:
  - Header: receipt URL (HUGE button), submission timestamp, payer logo
  - Trigger card: PDF preview + extracted patient fields
  - Loop steps: each ReAct iteration as a collapsible card with
    `plan → tool call → tool result`
  - Compliance card: Opsera scan result (PASS, list of fields checked)
  - Footer: 4 sponsor logos with a one-line "did what" per logo

## Data model

The schema is split into two subdomains with a formal boundary —
`agent_run` (the autonomous PA filing loop) and `clinic_form` (the
HealthFirst portal submission flow). See
[ADR 0005 — Data-model boundary](decisions/0005-data-model-boundary.md)
for ownership, rationale, and the optional cross-link.

The SQL below is the `agent_run` subdomain. The `clinic_form` subdomain
(`pa_submissions`) lives in
[`db/migrations/0002_add_pa_submissions.sql`](../db/migrations/0002_add_pa_submissions.sql) and
[`0003_add_pa_submissions_review_cols.sql`](../db/migrations/0003_add_pa_submissions_review_cols.sql).

```sql
-- patients: one row per demo patient (we'll seed 3)
CREATE TABLE patients (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name   TEXT NOT NULL,
  dob         DATE NOT NULL,
  plan_id     TEXT NOT NULL,             -- e.g. "UHC-CHOICE-PLUS"
  member_id   TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- prior_auths: one row per agent run
CREATE TABLE prior_auths (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id      UUID NOT NULL REFERENCES patients(id),
  drug_name       TEXT NOT NULL,
  drug_ndc        TEXT,
  dose            TEXT,
  diagnosis_code  TEXT,                  -- ICD-10
  status          TEXT NOT NULL DEFAULT 'pending',
                                         -- pending|submitted|approved|denied|error
  receipt_url     TEXT,                  -- payer confirmation URL
  trigger_pdf_key TEXT,                  -- Insforge storage key
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- agent_events: each ReAct step
CREATE TABLE agent_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id        UUID NOT NULL REFERENCES prior_auths(id),
  step_no      INT NOT NULL,
  verb         TEXT NOT NULL,            -- READ-WEB|EXECUTE|VERIFY|PERSIST
  plan         TEXT,                     -- model's plan for this step
  tool_input   JSONB,
  tool_output  JSONB,
  duration_ms  INT,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- pa_embeddings: RAG over past approvals (pgvector)
CREATE TABLE pa_embeddings (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id        UUID NOT NULL REFERENCES prior_auths(id),
  rationale    TEXT NOT NULL,            -- the medical-necessity letter
  embedding    VECTOR(1536) NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON pa_embeddings USING ivfflat (embedding vector_cosine_ops);

-- compliance_scans: Opsera VERIFY results
CREATE TABLE compliance_scans (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id         UUID NOT NULL REFERENCES prior_auths(id),
  passed        BOOLEAN NOT NULL,
  flagged_fields JSONB,
  raw_response  JSONB,
  scanned_at    TIMESTAMPTZ DEFAULT now()
);
```

## Sequence (end-to-end for one run)

```
User                  UI               Agent                Insforge   Rtrvr     Daytona   Opsera
 |                     |                  |                     |          |          |        |
 |--upload PDF-------->|                  |                     |          |          |        |
 |                     |--POST /run------>|                     |          |          |        |
 |                     |                  |--store PDF (storage)->|        |          |        |
 |                     |                  |--insert prior_auths-->|        |          |        |
 |                     |                  |  (status=pending)     |        |          |        |
 |                     |<--run_id---------|                     |          |          |        |
 |                     |                  |                     |          |          |        |
 |                     |                  | step 1: READ-WEB    |          |          |        |
 |                     |                  |--/agent (fetch UHC rule)----->|          |        |
 |                     |                  |<----rule json--------|--------|          |        |
 |                     |<-SSE step1-------|                     |          |          |        |
 |                     |                  |                     |          |          |        |
 |                     |                  | step 2: EXECUTE     |          |          |        |
 |                     |                  |--sandbox().exec(parse_pdf)-------------->|        |
 |                     |                  |<--{drug,dose,icd10}--|---------|----------|        |
 |                     |<-SSE step2-------|                     |          |          |        |
 |                     |                  |                     |          |          |        |
 |                     |                  | step 3: VERIFY      |          |          |        |
 |                     |                  |--MCP scan_pii(packet)--------------------------->|
 |                     |                  |<--{passed: true}-----|---------|----------|--------|
 |                     |<-SSE step3-------|                     |          |          |        |
 |                     |                  |                     |          |          |        |
 |                     |                  | step 4: ACTION      |          |          |        |
 |                     |                  |--/agent (fill+submit form)--->|          |        |
 |                     |                  |<----receipt_url------|--------|          |        |
 |                     |                  |--update prior_auths-->|        |          |        |
 |                     |                  |  (status=submitted)   |        |          |        |
 |                     |                  |--edge_fn(notify_doctor)>|       |          |        |
 |                     |<-SSE done--------|                     |          |          |        |
 |<--render /run/:id---|                  |                     |          |          |        |
 |                     |--GET /run/:id--->|                     |          |          |        |
 |                     |<--full audit-----|                     |          |          |        |
```

## Cache strategy

For the stage demo, fixture mode can replay cached sponsor responses so the
flow does not depend on conference Wi-Fi.

| Surface | What we cache | Where |
|---------|---------------|-------|
| UHC coverage rule | Pre-fetched JSON for our 3 demo `(drug, plan)` pairs | `assets/fixtures/uhc-rules.json` |
| PDF parsing | Daytona snapshot pre-baked with pdfplumber + transformers | Daytona snapshot ID in `.env` |
| Opsera scan | Pre-recorded "passed" + "flagged" responses, keyed by run scenario | `assets/fixtures/opsera-scans.json` |
| Rtrvr form fill | Pre-recorded `.har` of a successful UHC submission, replayed via local mock | `assets/fixtures/uhc-submit.har` |

## Fallback model (if a sponsor is red on demo morning)

| If down | What happens |
|---------|--------------|
| Rtrvr  | Switch to recorded `.har` replay through a local sandbox portal. Tell the judges; the audit page still renders. |
| Daytona | Run PDF parsing in-process; mention "Daytona is the production sandbox." Lose 1 sponsor logo. |
| Opsera | Show a pre-recorded scan result on the audit page; in Q&A, mention the live MCP call. |
| Insforge | Local Docker Postgres + pgvector. Lose the model-gateway demo beat. |
| Any 2+ down | Switch to the full recorded screencast. Don't apologize. |

## What we are NOT building

(Listed once here, planted in spec.md, named on stage.)

- Real payer auth flow
- EHR integration (Epic / Athena)
- HIPAA cert / SOC2 paperwork
- Multi-tenant isolation
- Denial appeals
- Mobile app
