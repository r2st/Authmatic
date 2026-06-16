# Authmatic — Team split report

**You:** mock insurer, demo data, UI, payer APIs, **simulated agent (working demo)**  
**Teammate:** swap fake agent steps for real sponsor integrations (FastAPI + Rtrvr + Daytona + Opsera)  
**Demo path:** Sarah Martinez → Ozempic → HealthFirst PPO → prior auth approved

---

## TL;DR for teammate

**Do not rebuild the portal, UI, or `/api/pa/*`.** A full demo agent already runs in `apps/web`. Your job is to **replace 3 simulated steps** (EXTRACT, VERIFY, SUBMIT) with real sponsor calls, then wire persistence. Match the existing SSE step format so `/run/[id]` keeps working.

**Start here:** [Exact instructions for teammate](#part-2--exact-instructions-for-teammate-do-these-in-order) (below)

---

## Part 1 — What is already done (you)

### Demo agent — **already working**

Click **Run demo** on `/` → full flow completes today:

| Step | Verb | Sponsor label | What happens **now** | Real? |
|------|------|---------------|----------------------|-------|
| 1 | EXTRACT | Daytona | Returns Sarah fixture from `demo-case.ts` | **Fake** |
| 2 | VERIFY | Opsera | Always `{ passed: true }` | **Fake** |
| 3 | SUBMIT | Rtrvr | Portal iframe + client autofill animation | **Fake** |
| 4 | ADJUDICATE | HealthFirst | Calls real `adjudicateReference()` + payer rules | **Real** |
| 5 | PERSIST | InsForge + Tigris | Submission to InsForge; Tigris referenced | **Partial** |

**Code that runs this today:**

| File | Role |
|------|------|
| `apps/agent/` (Python ReAct loop) | 5-step pipeline — proxied via `apps/web/src/lib/agent-proxy.ts` |
| `apps/web/src/lib/agent-runs.ts` | In-memory run + step state |
| `apps/web/src/app/api/stream/[id]/route.ts` | SSE stream to UI |
| `apps/web/src/app/api/run/route.ts` | `POST /api/run` → `run_id` |
| `apps/web/src/app/run/[id]/page.tsx` | Audit UI (steps + portal iframe) |

**Smoke test (works now on port 3001):**

```bash
cd apps/web && npm run dev   # note the port (often 3001)
# Open http://localhost:3001 → Run demo → watch /run/{id}
```

---

### Fake world (insurer, patient, clinic, Rx)

| Entity | Details |
|--------|---------|
| **Insurer** | HealthFirst PPO — mock portal, not a real payer |
| **Patient** | Sarah Martinez, DOB 03/14/1986, member `HF45821973`, T2D (E11.9) |
| **Clinic** | Bay Area Primary Care — Emily Chen, MD, Oakland |
| **Rx** | Ozempic 0.25mg weekly + step-therapy justification |
| **PDFs** | `assets/demo/patient_chart_sarah_martinez.pdf`, `prescription_ozempic_martinez.pdf` |
| **Fixture** | `fixtures/healthfirst-case.json` |

---

### UI (all done)

| Route | Purpose |
|-------|---------|
| `/` | Upload + Run demo |
| `/run/[id]` | Agent audit — SSE steps + portal iframe |
| `/portal/healthfirst/prior-auth` | PA form (Rtrvr targets this) |
| `/portal/healthfirst/submission/[ref]` | Status page (Pending → Approved) |

**Form selectors:** `#patient_name`, `#dob`, `#member_id`, `#diagnosis`, `#medication`, `#dosage`, `#provider_name`, `#justification`, `#submit-prior-auth`

---

### Payer APIs (done — teammate **calls** these, does not rebuild)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/pa/submit` | Create submission → `pending_review` |
| `GET` | `/api/pa/{ref}` | Poll status |
| `POST` | `/api/pa/{ref}/adjudicate` | Trigger payer review (~8s) → approved/denied |

Adjudication rules: `apps/web/src/lib/adjudication.ts`

---

### Data layer (partially done)

| System | Status |
|--------|--------|
| InsForge | Linked — `pa_submissions` wired; `prior_auths` + `agent_events` tables exist but agent doesn't write to them yet |
| Tigris | Client + upload script; agent-side upload not wired |

---

## Part 2 — Exact instructions for teammate (do these in order)

### Step 0 — Read these files first (30 min)

1. `apps/agent/` (Python ReAct loop) — **match this step shape** (old `agent-orchestrator.ts` deleted; see `agent-proxy.ts` for the web proxy)
2. `apps/web/src/lib/agent-runs.ts` — run/step types
3. `docs/healthfirst-portal-handoff.md` — portal URLs + API
4. `fixtures/healthfirst-portal.json` — Rtrvr selectors
5. `fixtures/healthfirst-case.json` — expected extracted fields

---

### Step 1 — Scaffold FastAPI (`apps/agent/`)

Create a minimal service:

```
apps/agent/
├── main.py              # FastAPI app
├── requirements.txt     # fastapi, uvicorn, httpx, ...
├── .env                 # copy from repo .env.example
└── agent/
    ├── pipeline.py      # runAgentPipeline equivalent
    ├── extract.py       # Daytona
    ├── verify.py        # Opsera
    ├── submit.py        # Rtrvr
    └── persist.py       # InsForge + Tigris
```

**Required endpoints:**

| Method | Path | Must return |
|--------|------|-------------|
| `GET` | `/health` | `{ "ok": true }` |
| `POST` | `/api/run` | `{ "run_id": "uuid", "demo": true }` |
| `GET` | `/api/run/{id}` | Full run object (same shape as `AgentRun` in `agent-runs.ts`) |
| `GET` | `/api/stream/{id}` | SSE — same event types as web app |

**Env vars (use actual dev port — often 3001, not 3000):**

```bash
WEB_URL=http://localhost:3001
PORTAL_URL=http://localhost:3001/portal/healthfirst/prior-auth
AGENT_URL=http://localhost:8000
DEMO_FIXTURE_MODE=true
# + RTRVR, DAYTONA, OPSERA, INSFORGE, TIGRIS keys from .env.example
```

---

### Step 2 — Match the SSE event contract

The UI on `/run/[id]` expects these SSE events. **Do not change the shape.**

```json
{ "type": "connected", "run_id": "..." }
```

```json
{
  "type": "step",
  "step": {
    "step_no": 1,
    "verb": "EXTRACT",
    "sponsor": "Daytona",
    "plan": "...",
    "status": "running" | "done",
    "tool_input": {},
    "tool_output": {},
    "duration_ms": 1800
  },
  "run": { "id": "...", "status": "running", "steps": [...] }
}
```

```json
{
  "type": "portal",
  "path": "/portal/healthfirst/prior-auth?autofill=1&run={run_id}"
}
```

```json
{ "type": "done", "run": { "status": "completed", "reference_id": "...", "receipt_url": "..." } }
```

```json
{ "type": "error", "message": "...", "run": { ... } }
```

Copy field names from `apps/web/src/lib/agent-runs.ts` → `AgentStep`, `AgentRun`.

---

### Step 3 — Replace EXTRACT (Daytona)

**Today:** orchestrator hardcodes `getDemoFormPayload()`.

**You build:**

1. Input: Sarah's PDFs from `assets/demo/` (or uploaded via `POST /api/run` multipart)
2. Call Daytona (or pdfplumber + LLM fallback) to extract fields
3. Output must be this exact shape:

```json
{
  "patient_name": "Sarah Martinez",
  "dob": "03/14/1986",
  "member_id": "HF45821973",
  "diagnosis": "Type 2 Diabetes (E11.9)",
  "medication": "Ozempic",
  "dosage": "0.25mg weekly",
  "provider_name": "Emily Chen, MD",
  "justification": "Poor glycemic control despite first-line therapy. HbA1c 8.9% on Metformin x18mo."
}
```

**Fallback:** if Daytona fails or `DEMO_FIXTURE_MODE=true`, use `fixtures/healthfirst-case.json`.

Emit SSE step 1 with `tool_output` = extracted payload.

---

### Step 4 — Replace VERIFY (Opsera)

**Today:** always `{ passed: true, flagged_fields: [] }`.

**You build:**

1. Send outgoing packet (extracted fields) to Opsera MCP / API
2. Emit SSE step 2 with real `tool_output`
3. If failed → emit `{ type: "error" }` and stop pipeline

---

### Step 5 — Replace SUBMIT (Rtrvr) — most important

**Today:** web sends `portal` SSE event → iframe runs client autofill.

**You build:**

1. Emit SSE `portal` event (UI may still show iframe — that's OK)
2. Call Rtrvr with this task:

```
Open {PORTAL_URL}.
Fill #patient_name, #dob, #member_id, #diagnosis, #medication,
#dosage, #provider_name, #justification with extracted data.
Click #submit-prior-auth.
Wait for URL matching /portal/healthfirst/submission/PA-*.
Return reference_id from URL.
```

3. **Do NOT rebuild the form.** Rtrvr uses our portal at `PORTAL_URL`.
4. Emit SSE step 3 with `tool_output`:

```json
{
  "reference_id": "PA-2026-00451",
  "status": "pending_review",
  "receipt_url": "{WEB_URL}/portal/healthfirst/submission/PA-2026-00451"
}
```

**Alternative:** Rtrvr submits the HTML form directly (no JSON). Either way, capture `reference_id` from redirect URL.

**Fallback:** if Rtrvr fails and `DEMO_FIXTURE_MODE=true`, call:

```bash
curl -X POST {WEB_URL}/api/pa/submit \
  -H "Content-Type: application/json" \
  -d '{ ...8 fields... }'
```

---

### Step 6 — ADJUDICATE (call our API — do not reimplement)

**Already real in web app.** You just call it:

```bash
curl -X POST {WEB_URL}/api/pa/{reference_id}/adjudicate \
  -H "Content-Type: application/json" \
  -d '{"review_delay_ms": 8000}'
```

Then poll until status is `approved` or `denied`:

```bash
curl {WEB_URL}/api/pa/{reference_id}
```

Emit SSE step 4 with result. **Do not copy adjudication logic** — it lives in `apps/web/src/lib/adjudication.ts`.

---

### Step 7 — PERSIST (InsForge + Tigris)

**Today:** submission goes to `pa_submissions` only; `agent_events` table is empty.

**You build:**

1. **InsForge** — on each step, insert into `agent_events`:

```sql
-- table: agent_events (see db/001_authmatic_schema.sql)
step_no, verb, plan, tool_input, tool_output, duration_ms
```

2. **InsForge** — insert/update `prior_auths` with `reference_id`, `receipt_url`, storage keys

3. **Tigris** — upload chart PDF, prescription PDF, receipt screenshot/JSON; save keys + URLs in `prior_auths`

Use same InsForge project: `https://z739c3mi.us-east.insforge.app` (keys in `.env.local`)

Emit SSE step 5 with storage paths.

---

### Step 8 — Wire web UI to your FastAPI

Pick **one** approach (discuss with teammate before coding):

**Option A — Proxy (recommended, less UI change):**  
Change `apps/web/src/app/api/stream/[id]/route.ts` to proxy SSE from `{AGENT_URL}/api/stream/{id}` when `AGENT_URL` is set.

**Option B — Direct:**  
Change `apps/web/src/app/page.tsx` to `POST {AGENT_URL}/api/run` instead of `/api/run`.

Either way: **keep `/run/[id]` and portal routes unchanged.**

---

### Step 9 — Deploy to Render

1. Deploy `apps/web` → public `WEB_URL`
2. Deploy `apps/agent` → public `AGENT_URL`
3. Set `PORTAL_URL={WEB_URL}/portal/healthfirst/prior-auth`
4. Test full flow on public URLs before demo

---

## Part 3 — What NOT to build (already done)

| Do NOT rebuild | Why |
|----------------|-----|
| HealthFirst portal UI | Done in `apps/web/src/app/portal/` |
| PA form field IDs | Stable Rtrvr contract |
| `/api/pa/submit`, `/api/pa/{ref}`, `/api/pa/{ref}/adjudicate` | Payer APIs done |
| `/run/[id]` audit page | SSE consumer done |
| Adjudication / approval rules | Done in `adjudication.ts` |
| Sarah demo data + PDFs | Done in `mock/` + `assets/demo/` |
| Full agent loop skeleton | Done in `apps/agent/` (Python ReAct loop); web proxies via `agent-proxy.ts` |

---

## Part 4 — Acceptance checklist (teammate done when…)

- [ ] `GET http://localhost:8000/health` returns OK
- [ ] `POST /api/run` → `run_id`; `GET /api/stream/{id}` streams 5 steps
- [ ] Step 1 EXTRACT returns 8 fields from PDFs (or fixture fallback)
- [ ] Step 2 VERIFY calls Opsera (or stub with real HTTP call)
- [ ] Step 3 SUBMIT uses Rtrvr against `{PORTAL_URL}` and returns real `reference_id`
- [ ] Step 4 calls `{WEB_URL}/api/pa/{ref}/adjudicate` → approved for Sarah demo
- [ ] Step 5 writes rows to `agent_events` + `prior_auths` in InsForge
- [ ] PDFs/receipt uploaded to Tigris with URLs in InsForge
- [ ] `/run/[id]` UI still works with your SSE events
- [ ] `DEMO_FIXTURE_MODE=true` fallback works if Rtrvr fails on stage
- [ ] Both services deployed to Render with public URLs

---

## Part 5 — Boundary diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  YOU — DONE                                                      │
│  • HealthFirst portal + form (#patient_name … #submit-prior-auth)│
│  • Sarah demo data + PDFs                                        │
│  • /api/pa/submit · /api/pa/{ref} · /api/pa/{ref}/adjudicate     │
│  • Home + /run/[id] UI + SSE consumer                            │
│  • Simulated agent (orchestrator) — WORKING DEMO                 │
│  • InsForge pa_submissions + adjudication rules                  │
└──────────────────────────────────────────────────────────────────┘
         │  PORTAL_URL                    │  /api/pa/{ref}/adjudicate
         ▼                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  TEAMMATE — REPLACE 3 FAKE STEPS + PERSIST                       │
│  1. EXTRACT  → Daytona (PDF → 8 fields)                          │
│  2. VERIFY   → Opsera                                            │
│  3. SUBMIT   → Rtrvr (fill portal, get reference_id)            │
│  4. ADJUDICATE → call our API (already built)                    │
│  5. PERSIST  → InsForge agent_events + prior_auths, Tigris upload│
│  FastAPI in apps/agent/ · Render deploy                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 6 — Reference docs

| File | Purpose |
|------|---------|
| [docs/healthfirst-portal-handoff.md](./healthfirst-portal-handoff.md) | Portal URLs, selectors, API examples |
| [fixtures/healthfirst-portal.json](../fixtures/healthfirst-portal.json) | Machine-readable Rtrvr spec |
| [fixtures/healthfirst-case.json](../fixtures/healthfirst-case.json) | Demo patient fixture |
| [apps/agent/README.md](../apps/agent/README.md) | Teammate quick reference |
| [docs/insforge.md](./insforge.md) | DB schema + InsForge setup |
| [docs/tigris.md](./tigris.md) | File storage setup |

---

## Summary

**You:** Full demo works today — fake insurer, patient, UI, payer APIs, and a **simulated 5-step agent** that streams to `/run/[id]`.

**Teammate:** Build `apps/agent/` FastAPI service. **Swap EXTRACT, VERIFY, SUBMIT** for real Daytona/Opsera/Rtrvr. **Call** our adjudicate API for step 4. **Write** InsForge `agent_events` + Tigris uploads for step 5. Match existing SSE format. Do not rebuild portal or payer logic.
