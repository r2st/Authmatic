# Authmatic — Demo Plan

> 3-minute pitch. Sarah Martinez → Ozempic → HealthFirst. Mock portal, real Rtrvr.

## Slot

3 minutes (target 2:45) + Q&A.

## Pitch script

### 0:00 – 0:30 — Problem

> "Every week, medical assistants spend hours on prior authorizations — reading
> the chart, reading the prescription, filling an insurer form, uploading
> documents, hitting submit. Sarah Martinez needs Ozempic for her diabetes.
> Her clinic has the chart and the script. What they don't have is nine hours
> to re-type it all into HealthFirst's portal."

### 0:30 – 0:45 — Solution

> "We built Authmatic: drop the PDFs, the agent extracts the data, drives the
> insurer portal in a real browser, submits, and returns a receipt — in ninety
> seconds."

### 0:45 – 2:30 — Live demo

| Time | Screen | What you say |
|------|--------|--------------|
| 0:45 | Dropzone | "Maria drops Sarah's chart and prescription. Two files. That's her whole job from here." |
| 0:55 | Upload confirms | "Patient record uploaded. Prescription uploaded." |
| 1:00 | Agent stream — EXTRACT | "The agent reads the chart — diagnosis, medication, provider, insurance." |
| 1:20 | Rtrvr fills mock portal | "Rtrvr opens HealthFirst's portal in a real browser. Watch the fields fill." |
| 1:45 | Submit → success | "Submit. Authorization submitted. Reference ID PA-2026-00451." |
| 2:00 | `/run/:id` audit | "Receipt at the top. Full audit chain. Stored in Tigris, tracked in InsForge, live on Render." |

### 2:30 – 3:00 — Close

> "One workflow. Real browser automation. Full audit trail. Happy to walk through
> how we'd add the next payer."

---

## Q&A (top 5)

| Question | Answer |
|----------|--------|
| "Is HealthFirst real?" | Demo uses a mock portal we host — production would target real payer URLs. Pattern is identical. |
| "How does this scale across payers?" | Each portal is a Rtrvr task template. ~2 hours per new payer form. |
| "What about HIPAA?" | Synthetic demo data only. Production: BAA + encrypted storage (Tigris) + audited logs (InsForge). |
| "Is this just Selenium?" | No — agent decides what to extract, maps fields, and submits. Browser is the action layer. |
| "What if the form changes?" | Rtrvr adapts to DOM layout. We version the mock portal to match. |

---

## Fallback plan

### Recording

- **File:** `demo/recordings/prior-auth-happy-path.mp4`
- Record after happy path works on demo laptop
- Narrate live over it if Rtrvr flakes

### If something breaks

| Breaks | Action |
|--------|--------|
| Rtrvr hangs | "Live browser automation is brittle on conference WiFi — here's the recording." |
| InsForge down | Audit page reads local fallback JSON |
| Whole network | localhost + recording |

### Pre-pitch checklist

- [ ] Render URL loads in < 2s
- [ ] Demo PDFs in `assets/demo/` ready to drag
- [ ] Mock portal `/portal/healthfirst/prior-auth` loads standalone
- [ ] Recording plays in QuickTime
- [ ] Notifications off, fresh browser profile

---

## Sponsor mention checklist

- [ ] **Rtrvr** — named during form fill, visible on stream card
- [ ] **Tigris** — "stored in Tigris" on audit page
- [ ] **InsForge** — "workflow tracked in InsForge" on audit page
- [ ] **Render** — live URL said out loud + in README
