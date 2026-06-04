# Authmatic — Architecture

> Mock insurer portal + real browser automation. Sarah Martinez demo path.

## System diagram

```
┌─────────────────────────────────────────────────────────────┐
│  apps/web (Next.js on Render)                    YOU        │
│  ─ /              dropzone (chart + rx PDFs)                │
│  ─ /run/:id       live stream + audit page                  │
│  ─ /portal/healthfirst/prior-auth   ◀── Rtrvr target       │
│  ─ /portal/healthfirst/success      ◀── receipt page       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  apps/agent (FastAPI on Render)                  TEAMMATE    │
│  ─ POST /api/run                                              │
│  ─ GET  /api/stream/:id  (SSE)                                │
│  ─ GET  /api/run/:id                                          │
└──────┬─────────────┬──────────────┬─────────────────────────┘
       │             │              │
   EXTRACT       SUBMIT         PERSIST
       │             │              │
       ▼             ▼              ▼
  pdfplumber/    ┌─────────┐   ┌──────────────────────────┐
  LLM + fixture  │ Rtrvr   │   │ InsForge                 │
                 │ /agent  │   │ Postgres + Storage       │
                 │ fills   │   │ pa_submissions, PDFs,    │
                 │ mock    │   │ prior_auths, agent_events│
                 │ portal  │   └──────────────────────────┘
```

## Components

| Component | Owner | Tech | Purpose |
|-----------|-------|------|---------|
| Web UI + portal | You | Next.js + Tailwind | Dropzone, audit, **mock HealthFirst form** |
| Agent service | Teammate | FastAPI | Extract, orchestrate Rtrvr, persist |
| Object storage | Both | **Tigris** | PDFs, receipts (S3-compatible) |
| Workflow DB | Both | **InsForge** | Submissions, runs, agent_events |
| Browser agent | Teammate | Rtrvr | Fill + submit mock portal |
| Hosting | Either | Render | Public demo URL |

## Agent loop (demo — 4 steps)

| Step | Verb | Sponsor | What happens |
|------|------|---------|--------------|
| 1 | EXTRACT | — | Parse chart + rx PDFs → structured fields |
| 2 | PREPARE | InsForge | Create run record, log plan |
| 3 | SUBMIT | Rtrvr | Open mock portal, fill fields, click Submit → **Pending Review** |
| 4 | ADJUDICATE | Mock payer API | `POST /api/pa/{ref}/adjudicate` — medical review → Approved/Denied |
| 5 | PERSIST | InsForge | Store receipt, PDFs, agent_events |

Stream each step to UI via SSE.

## Mock portal contract

Rtrvr and the form **must agree on field names**. Defined in `fixtures/healthfirst-case.json`:

| Field ID | Example value |
|----------|---------------|
| `patient_name` | Sarah Martinez |
| `dob` | 03/14/1986 |
| `member_id` | HF45821973 |
| `diagnosis` | Type 2 Diabetes (E11.9) |
| `medication` | Ozempic |
| `dosage` | 0.25mg weekly |
| `provider_name` | Emily Chen, MD |
| `justification` | Poor glycemic control despite first-line therapy |

Success page URL: `/portal/healthfirst/submission/PA-2026-00451` (starts **Pending Review**, not approved)

Adjudication (agent calls after submit):

```bash
POST /api/pa/PA-2026-00451/adjudicate
# → under_review (~8s) → approved or denied
```

## Data model (InsForge)

```sql
CREATE TABLE prior_auths (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_name    TEXT NOT NULL,
  drug_name       TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending',
  reference_id    TEXT,
  receipt_url     TEXT,
  chart_key       TEXT,
  prescription_key TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_id        UUID NOT NULL REFERENCES prior_auths(id),
  step_no      INT NOT NULL,
  verb         TEXT NOT NULL,
  plan         TEXT,
  tool_input   JSONB,
  tool_output  JSONB,
  duration_ms  INT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

## Sequence

```
User → upload PDFs → POST /api/run → run_id
     → SSE stream: EXTRACT → PREPARE → SUBMIT → PERSIST
     → Rtrvr fills /portal/healthfirst/prior-auth → success page
     → /run/:id shows receipt + audit trail
```

## Fallback

| If down | Action |
|---------|--------|
| Rtrvr | `DEMO_FIXTURE_MODE=true` + pre-recorded form-fill clip |
| InsForge | Local JSON fallback for `/run/:id` only |
| Render | localhost demo + recording |

## Not building

- Real payer portals (UHC, Aetna, etc.)
- EHR / Epic integration
- Multi-patient / multi-payer demo
- HIPAA certification paperwork
