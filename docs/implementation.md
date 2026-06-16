# Authmatic — Implementation Plan

> Build order for hackathon day. Mock portal first, then wire sponsors.

## Team ownership

| Phase | You | Teammate |
|-------|-----|----------|
| H+0–1 | Mock portal + dropzone UI | FastAPI skeleton + `/api/run` stub |
| H+1–2 | Audit page layout + SSE consumer | PDF extract + InsForge schema |
| H+2–3 | Portal field IDs locked | Rtrvr → mock portal integration |
| H+3–4 | Polish UI, deploy web to Render | Tigris + InsForge persist, deploy agent |
| H+4+ | Recording, dry-runs | Fixture fallback, smoke tests |

---

## Pre-build

```bash
cp .env.example .env
# Fill: INSFORGE_*, TIGRIS_*, RTRVR_*, WEB_URL, PORTAL_URL
```

Demo data: `fixtures/healthfirst-case.json`
Demo PDFs: `assets/demo/*.pdf`

---

## H+0 → H+1 — Skeleton

**You:**
- [ ] `apps/web` — Next.js app boots
- [ ] `/portal/healthfirst/prior-auth` — form with 8 fields (see architecture.md)
- [ ] `/portal/healthfirst/success?ref=` — confirmation page
- [ ] `/` — dropzone (chart + rx, two files)

**Teammate:**
- [ ] `apps/agent` — FastAPI boots
- [ ] `POST /api/run` → `{ run_id }`
- [ ] `GET /api/stream/:id` → SSE stub (4 steps)
- [ ] `GET /health` → 200

**Both:** Agree on field IDs in portal ↔ `fixtures/healthfirst-case.json`.

---

## H+1 → H+2 — Happy path (fixtures)

**Teammate:**
- [ ] EXTRACT step — pdfplumber or LLM; fallback to `healthfirst-case.json`
- [ ] InsForge tables: `prior_auths`, `agent_events`
- [ ] SSE emits EXTRACT → PREPARE → SUBMIT → PERSIST

**You:**
- [ ] `/run/[id]` — receipt banner first, then step cards
- [ ] Subscribe to SSE; render steps as they arrive
- [ ] "Load demo files" button → preloads Sarah's PDFs

---

## H+2 → H+3 — Wire sponsors (one at a time)

1. [ ] **Rtrvr** → `PORTAL_URL` (your mock form). Test fill + submit manually.
2. [ ] **Tigris** → upload PDFs on `/api/run`, receipt JSON on PERSIST.
3. [ ] **InsForge** → write agent_events; `/api/run/:id` reads from DB.
4. [ ] **Render** → deploy both services; update `PORTAL_URL` to public URL.

Keep `DEMO_FIXTURE_MODE=true` path as fallback after each real integration.

---

## H+3 → H+4 — Money shot

- [ ] Receipt reference ID pinned at top of `/run/:id`
- [ ] Sponsor one-liners in audit footer (Rtrvr, Tigris, InsForge, Render)
- [ ] Record `demo/recordings/prior-auth-happy-path.mp4`

---

## Rtrvr task (copy-paste shape)

```python
async def submit_pa_form(portal_url: str, fields: dict) -> dict:
    task = (
        f"Open {portal_url}. Fill the prior authorization form: "
        f"patient_name={fields['patient_name']}, "
        f"dob={fields['dob']}, member_id={fields['member_id']}, "
        f"diagnosis={fields['diagnosis']}, medication={fields['medication']}, "
        f"dosage={fields['dosage']}, provider_name={fields['provider_name']}, "
        f"justification={fields['justification']}. "
        "Click Submit. Return the reference ID from the success page URL."
    )
    # POST to Rtrvr /agent with schema: { reference_id, receipt_url }
```

---

## Run-through checklist (done = stop building)

- [ ] Drag both PDFs from `assets/demo/` onto dropzone
- [ ] 4 SSE steps appear within 90s
- [ ] Rtrvr fills mock portal (or recording plays)
- [ ] Success page shows `PA-2026-00451`
- [ ] `/run/:id` — receipt first, audit chain visible
- [ ] Render URL loads on conference WiFi
- [ ] Recording exists as fallback

If all pass: stop building. Polish only.
