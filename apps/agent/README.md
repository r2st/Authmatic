# Agent service (FastAPI)

**Owner:** Teammate  
**Integration surface:** mock HealthFirst portal in `apps/web` — see **[docs/healthfirst-portal-handoff.md](../../docs/healthfirst-portal-handoff.md)**

**Machine-readable portal spec:** [`fixtures/healthfirst-portal.json`](../../fixtures/healthfirst-portal.json)

---

## Your job

Build the real agent loop on top of the mock insurer portal (already built):

1. **EXTRACT** — parse Sarah's PDFs (Daytona / pdfplumber + LLM)
2. **VERIFY** — Opsera compliance scan before submit
3. **SUBMIT** — Rtrvr opens `PORTAL_URL`, fills 8 fields, clicks `#submit-prior-auth`
4. **ADJUDICATE** — call `POST /api/pa/{ref}/adjudicate` (submit does NOT auto-approve)
5. **PERSIST** — InsForge workflow + Tigris receipt

---

## Portal URLs (do not hit real payers)

| URL | Purpose |
|-----|---------|
| `{WEB_URL}/portal/healthfirst/prior-auth` | **Form Rtrvr fills** |
| `{WEB_URL}/portal/healthfirst/submission/{ref}` | Status page after submit |
| `{WEB_URL}/run/{run_id}` | Audit UI (already in Next.js) |

Set in `.env`:

```bash
WEB_URL=http://localhost:3000
PORTAL_URL=http://localhost:3000/portal/healthfirst/prior-auth
```

Use the port your Next.js dev server actually runs on.

---

## Form selectors (Rtrvr)

| Field | Selector | Demo value |
|-------|----------|------------|
| Patient Name | `#patient_name` | Sarah Martinez |
| DOB | `#dob` | 03/14/1986 |
| Member ID | `#member_id` | HF45821973 |
| Diagnosis | `#diagnosis` | Type 2 Diabetes (E11.9) |
| Medication | `#medication` | Ozempic |
| Dosage | `#dosage` | 0.25mg weekly |
| Provider | `#provider_name` | Emily Chen, MD |
| Justification | `#justification` | Poor glycemic control despite first-line therapy… |
| Submit | `#submit-prior-auth` | — |

Full list + API examples: [`fixtures/healthfirst-portal.json`](../../fixtures/healthfirst-portal.json)

---

## Rtrvr task prompt

```
Open {PORTAL_URL}. Fill: patient_name, dob, member_id, diagnosis,
medication, dosage, provider_name, justification. Click #submit-prior-auth.
Wait for redirect to /portal/healthfirst/submission/PA-*.
Return the reference_id from the URL.
```

---

## APIs you call (web app — already built)

| Method | Path | When |
|--------|------|------|
| `POST` | `/api/pa/submit` | Optional — Rtrvr can submit via form instead |
| `GET` | `/api/pa/{ref}` | Poll status |
| `POST` | `/api/pa/{ref}/adjudicate` | **After submit** — runs payer review (~8s) |

Or implement your own agent endpoints and have the web UI call you:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/run` | Accept PDFs, return `run_id` |
| `GET` | `/api/run/{id}` | Full audit payload |
| `GET` | `/api/stream/{id}` | SSE agent steps |
| `GET` | `/health` | Smoke test |

Today these live in `apps/web` as a **simulated** agent. Teammate can either:
- **Option A:** Replace orchestrator — web proxies to FastAPI at `AGENT_URL`
- **Option B:** Move SSE + run logic entirely into FastAPI

---

## Fixture fallback

When `DEMO_FIXTURE_MODE=true`, skip live Rtrvr and return canned receipt `PA-2026-00451`.

Demo payload source: `fixtures/healthfirst-case.json` and `apps/web/src/lib/demo-case.ts`.

---

## Smoke test (portal only, no FastAPI yet)

```bash
# Terminal 1
cd apps/web && npm run dev

# Terminal 2 — test adjudication after manual form submit
curl -X POST http://localhost:3000/api/pa/PA-2026-00451/adjudicate \
  -H "Content-Type: application/json" \
  -d '{"review_delay_ms": 3000}'
```

---

## Docs

| File | Purpose |
|------|---------|
| [docs/healthfirst-portal-handoff.md](../../docs/healthfirst-portal-handoff.md) | **Start here** — URLs, form, API, flow |
| [fixtures/healthfirst-portal.json](../../fixtures/healthfirst-portal.json) | Machine-readable selectors + API |
| [fixtures/healthfirst-case.json](../../fixtures/healthfirst-case.json) | Sarah Martinez demo data |
| [spec.md](../../spec.md) | Features + acceptance criteria |
| [architecture.md](../../architecture.md) | System design |
| [docs/insforge.md](../../docs/insforge.md) | Database tables |
| [docs/tigris.md](../../docs/tigris.md) | PDF storage |
