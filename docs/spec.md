# Authmatic — Spec

> Functional spec. One demo path. Sarah Martinez → Ozempic → HealthFirst.

## Customer

**Primary persona:** Maria, medical assistant at Dr. Chen's clinic in Oakland.
She files prior auths by hand into payer portals with no API.

**Demo patient:** Sarah Martinez — synthetic data only (see `fixtures/healthfirst-case.json`).

## Problem (one slice)

> Given a patient chart + prescription PDF that needs prior auth,
> the agent extracts fields, fills the payer form, submits, and returns a receipt.

**Not solving:** appeals, multi-drug bundling, real EHR integration, real payer SSO.

## User stories (priority order)

1. **Submit one prior auth end-to-end** *(P0 — the demo)*
   - Upload chart + prescription PDFs.
   - Agent stream shows extract → fill → submit steps.
   - Receipt URL + reference ID within ~90 seconds.

2. **Full audit page** *(P0 — money shot)*
   - `/run/:id` shows trigger PDFs, each agent step, receipt, sponsor artifacts.

3. ~~Re-run different drug/payer~~ *(cut for hackathon — one path only)*

4. Doctor approval before submit *(P2 — skip)*

## Features

| Feature | Owner | Must work? |
|---------|-------|------------|
| PDF dropzone | You | Yes |
| Mock HealthFirst portal | You | Yes |
| Agent SSE stream | Teammate | Yes |
| `/run/:id` audit page | You + teammate | Yes |
| Rtrvr form fill on mock portal | Teammate (you help) | Yes |
| Tigris storage | Teammate | Yes |
| InsForge workflow log | Teammate | Yes |
| Render deploy | Either | Yes |

## Non-goals

1. **Real payer login** — mock portal at `/portal/healthfirst/*`
2. **EHR integration** — PDF upload trigger only
3. **Multi-patient demo** — Sarah Martinez only until pitch-ready
4. **Denial appeals** — submit only

## Acceptance criteria

- [ ] Both PDFs in → reference ID out in < 120s on demo laptop
- [ ] Rtrvr visibly fills mock portal (or recording fallback)
- [ ] `/run/:id` shows receipt first, then full audit chain
- [ ] Tigris + InsForge artifacts visible on audit page
- [ ] Live Render URL works on conference WiFi
- [ ] Fallback recording in `demo/recordings/`

## Demo data

All extractable fields live in `fixtures/healthfirst-case.json`:

- Patient: Sarah Martinez, DOB 03/14/1986, Member ID HF45821973
- Insurance: HealthFirst PPO
- Diagnosis: Type 2 Diabetes (E11.9), A1c 8.9%
- Medication: Ozempic 0.25mg weekly
- Provider: Emily Chen, MD
- Justification: Poor glycemic control despite first-line Metformin
