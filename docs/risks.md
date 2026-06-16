# Authmatic — Risks & Gotchas

> Re-read before dry-runs. Mock portal = fewer surprises than real payers.

## Hot list (top 5)

| # | Risk | Mitigation |
|---|------|------------|
| 1 | Rtrvr can't find form fields (wrong `id`/`name`) | Field IDs must match `fixtures/healthfirst-case.json` exactly |
| 2 | Conference WiFi kills Rtrvr mid-demo | Pre-record form-fill clip; `DEMO_FIXTURE_MODE=true` fallback |
| 3 | Portal URL wrong in prod (localhost vs Render) | Set `PORTAL_URL` in `.env` to full public URL before deploy |
| 4 | SSE stream dies before final event | `/run/:id` re-fetches from InsForge on mount |
| 5 | PDF extraction fails on stage | Fixture fallback to `fixtures/healthfirst-case.json` values |

---

## Sponsor-specific

### Rtrvr

- **Field mismatch.** Mock portal uses `patient_name`; Rtrvr task must use same names.
- **Timeout.** Form fill can take 60–180s. Set SSE heartbeats so UI doesn't look frozen.
- **Free tier queue.** Don't re-run live in Q&A — show recording.

### Tigris

- **Bucket not public.** Receipt links need signed URLs or public-read on demo bucket.
- **Upload fails silently.** Log Tigris key on every persist step.

### InsForge

- **Cold start / DB unreachable.** Ship local JSON fallback for audit page.
- **Ask mentor** how they want workflow logs structured.

### Render

- **Two services.** Web + agent need separate Render services or monorepo deploy.
- **Env vars.** `PORTAL_URL` must be the Render web URL, not localhost.

---

## Demo-day operational

- **WiFi:** Hotspot backup ready
- **Browser extensions:** Fresh profile, no autofill interfering with Rtrvr
- **Time slip:** Pitch over 3:00 = judges cut you. Dry-run twice on the clock.
- **Scope creep:** One patient (Sarah). No second payer until happy path recorded.

---

## Red-amber-green (T-30 min)

| Component | Check | Red action |
|-----------|-------|------------|
| Mock portal | Loads at public URL | Fix Render deploy first |
| Rtrvr | Fills all 8 fields on mock portal | Switch to recording |
| Tigris | Upload returns a key | Show local path in audit |
| InsForge | `/api/run/:id` returns events | Local JSON fallback |
| Recording | Plays start-to-finish | Re-record from current build |

---

## Data & privacy

- All demo data is **synthetic** (Sarah Martinez).
- Do not use real PHI in PDFs or on screen during pitch.
