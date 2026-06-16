# Claude prompt — Authmatic slide deck

Copy everything below the line into Claude (or another slide generator).

---

Create a **10–12 slide** pitch deck for **Authmatic**, a healthcare hackathon project. Style: clean, professional, dark navy + warm orange accent (clinic UI colors). Include speaker notes per slide. Audience: hackathon judges with 3 minutes live demo after.

## Project facts

- **Repo (canonical):** https://github.com/r2st/Authmatic
- **Team:** Gulnoza Usmonova + Subhendu Das
- **Track:** Healthcare
- **Tagline:** An autonomous agent that files prior authorizations in ~90 seconds with a full audit trail.
- **Problem:** Medical assistants spend hours re-typing chart + Rx data into insurer prior-auth portals.
- **Solution:** Drop PDFs → agent extracts → verifies PHI → fills payer form → submits → returns receipt URL + audit page.

## Architecture (merged repo — what we actually ship)

The repo combines **two stacks** (both present on `main`):

### A. Live demo path (what judges see) — Next.js in-process agent
`apps/agent/` — Python ReAct loop (formerly scripted in the now-deleted `agent-orchestrator.ts`; web proxies via `agent-proxy.ts`):

| Step | Sponsor | Code | What it does |
|------|---------|------|--------------|
| 1 EXTRACT | **Daytona** | `lib/sponsors/daytona-extract.ts` | PDF → structured PA fields. `@daytonaio/sdk` ephemeral Python sandbox when `DAYTONA_API_KEY` set; else pdf-parse / fixture mode. |
| 2 VERIFY | **Opsera** | `lib/sponsors/opsera-verify.ts` | PHI scan before submit. MCP at `agent.opsera.ai/mcp` when `OPSERA_API_TOKEN` valid; else local HIPAA rules (SSN regex, field allowlist). |
| 3 SUBMIT | **Rtrvr** | `lib/sponsors/rtrvr-submit.ts` | `POST https://api.rtrvr.ai/agent` fills HealthFirst mock portal. Localhost → visible iframe autofill fallback (Rtrvr cloud blocks local URLs). |
| 4 ADJUDICATE | Mock payer | `lib/adjudication.ts` | Simulated approve/deny (not a sponsor). |
| 5 PERSIST | **InsForge + Tigris** | `lib/submissions.ts`, `lib/tigris/persist-run.ts` | InsForge `@insforge/sdk` → `pa_submissions`, `prior_auths`. Tigris S3 (`t3.storage.dev`) → chart PDF, Rx PDF, receipt JSON per run. |

### B. Original stack (still in repo) — FastAPI ReAct agent
`apps/agent` — Subhendu's 4-verb loop: READ-WEB (Rtrvr), EXECUTE (Daytona), VERIFY (Opsera MCP), PERSIST (Insforge Postgres + pgvector). Requires Docker Postgres + `make dev`. **Not the primary live demo path.**

## Sponsors — honest “real vs fallback” for presentation

Use this table in a slide. Be truthful with judges.

| Sponsor | Integrated? | Actually live in our demo env | What to say on stage |
|---------|-------------|-------------------------------|----------------------|
| **InsForge** | ✅ Yes | **REAL** — API writes to cloud project (`pa_submissions`, `prior_auths`, dashboard) | "Every submission is durable in InsForge — judges can see it on the dashboard." |
| **Tigris** | ✅ Yes (Gulnoza merge) | **REAL** — PDFs + receipt JSON uploaded to `authmatic-demo` bucket | "Patient documents and receipts land in Tigris — show keys on the run audit page." |
| **Rtrvr** | ✅ Yes | **REAL API call**; browser fill = iframe autofill on localhost, cloud browser on public deploy | "Rtrvr is our browser automation layer — you watch the form fill live in the iframe." |
| **Opsera** | ✅ Yes | **Local PHI rules** unless valid MCP token; MCP wired in code | "Opsera VERIFY gates the packet — Maria Santos demo shows SSN blocked before submit." |
| **Daytona** | ✅ Yes | **Wired** (`@daytonaio/sdk`); demo uses `DEMO_FIXTURE_MODE=true` + fixture extract for reliability | "Daytona runs PDF extraction in an ephemeral sandbox; we use fixture mode for demo stability." |

**Not sponsors:** HealthFirst portal = mock we host. Adjudication = simulated payer review.

**SUBMISSION.md note:** Tigris was listed as "stretch" in original submission — **now implemented**. Mark Tigris ✅ for final submission form.

## Live demo script (4 patients in parallel)

1. Login: `ma@bayarea-care.com` / `demo123`
2. Home `/` — 4 patients with PDFs: Sarah Martinez (Ozempic), James Wilson (Lisinopril), Robert Kim (Humira), Lisa Patel (Mounjaro)
3. Click **"Run 4 patients in parallel"** → `/batch/{id}`
4. Each agent: EXTRACT → VERIFY → SUBMIT (iframe form fill) → receipt
5. Dashboard — click reference IDs → submission summary
6. Optional safety beat: Maria Santos — Opsera blocks SSN, no receipt

## Demo patients

| Name | Drug | Member ID |
|------|------|-----------|
| Sarah Martinez | Ozempic 0.25mg weekly | HF45821973 |
| James Wilson | Lisinopril 10mg daily | HF88210456 |
| Robert Kim | Humira 40mg q2 weeks | HF77190234 |
| Lisa Patel | Mounjaro 2.5mg weekly | HF66501892 |

Each has `demo/pdfs/patient_chart_*.pdf` + `prescription_*.pdf`.

## Key URLs / pages

- `/` — patient picker + batch run
- `/run/{id}` — agent audit + portal iframe + Tigris artifacts
- `/batch/{id}` — parallel run status
- `/dashboard` — submissions from InsForge
- `/portal/healthfirst/submission/{ref}` — PA receipt
- `/security` — Opsera verify log

## Differentiators (slide bullets)

- Does not chat — **acts**: real form, real submission record, real receipt URL
- **Parallel batch**: 4 prior auths at once — scales the clinic workflow story
- Full audit chain on `/run/{id}` — every step, sponsor, duration, tool I/O
- PHI scoped to payer fields; VERIFY before submit
- **5 sponsors** in one loop: Daytona, Opsera, Rtrvr, InsForge, Tigris

## Q&A prep

| Question | Answer |
|----------|--------|
| Is HealthFirst real? | Mock portal we host; same PA form layout as real payers. Rtrvr pattern identical for production URLs. |
| HIPAA? | Synthetic patients only. Production = BAA + Tigris encryption + InsForge audit. |
| Just Selenium? | No — agent extracts, verifies, maps fields, submits. Rtrvr is the action layer. |
| FastAPI or Next.js? | Both in repo. Live demo uses Next.js in-process agent; FastAPI ReAct is the original architecture. |
| Scale to more payers? | ~2 hours per payer as Rtrvr task template. |

## Slide outline to generate

1. **Title** — Authmatic + team + tagline
2. **Problem** — 9 hours → 90 seconds (medical assistant pain)
3. **Solution** — one screenshot/mock: drop PDFs → receipt
4. **Architecture diagram** — 5 steps × 5 sponsors (Daytona, Opsera, Rtrvr, InsForge, Tigris)
5. **Sponsor table** — real vs fallback (honest)
6. **Live demo** — 4 patients parallel (Sarah, James, Robert, Lisa)
7. **Audit trail** — `/run/{id}` + InsForge dashboard + Tigris storage
8. **Safety** — Maria Santos / Opsera PHI block
9. **What's next** — more payers, doctor SMS approval, NEAR TEE
10. **Thank you** — github.com/r2st/Authmatic + QR

## Tone

Confident, honest, clinician-friendly. Lead with visible form autofill + batch parallel runs. Do not overclaim Opsera MCP or Daytona sandbox if running fixture mode — say "integrated with graceful fallback for demo reliability."

Generate the slide deck with speaker notes and suggested visuals (diagrams, bullet density, one demo screenshot placeholder per slide).
