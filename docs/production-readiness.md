# Production readiness checklist

Every remaining step to take Authmatic from "code-complete + browser-verified
locally" to "running in production." The code is done and tested; the items
below are **configuration, infrastructure, and legal** — they need
credentials, hosted services, or a human signature, none of which can be done
from the repo.

Legend: **[ops]** human/infra · **[legal]** signature/policy · **[code]** a
bounded follow-up code change. Phases are ordered — don't process real PHI
until Phase 2 is fully green.

---

## Phase 0 — Secrets & config (blockers for any deploy)

| # | Item | How | Owner |
|---|------|-----|-------|
| 0.1 | `SESSION_SECRET` (≥16 chars) | `openssl rand -base64 32` → set per env. App refuses to boot in prod without it. | [ops] |
| 0.2 | `AGENT_SERVICE_TOKEN` | `openssl rand -base64 32` → set on web **and** agent. Agent fails closed without it (ADR 0005). | [ops] |
| 0.3 | InsForge keys | `INSFORGE_PROJECT_URL` + `INSFORGE_API_KEY` from the InsForge dashboard. | [ops] |
| 0.4 | `AUTHMATIC_ENV=production` per service | Render service env (ticket 0019). Enables the prod guards. | [ops] |
| 0.5 | Confirm demo shortcuts OFF in prod | `DEMO_FIXTURE_MODE` / `USE_INPROCESS_AGENT` must be unset/false — the agent asserts this at startup. | [ops] |
| 0.6 | Secrets vault | Provision **Doppler** (ADR 0012); move all values off `.env`; wire Doppler→Render. | [ops] |
| 0.7 | Scan git history for leaked secrets | `gitleaks detect --source . --log-opts="--all"`; rotate anything found. | [ops] |

## Phase 1 — Database

| # | Item | How | Owner |
|---|------|-----|-------|
| 1.1 | Apply migrations to staging **and** prod | `INSFORGE_DB_URL=<env> make migrate` then `make migrate-status` (ticket 0035; 0001–0012 verified locally). | [ops] |
| 1.2 | Create the RLS app role | `ALTER ROLE authmatic_app LOGIN PASSWORD '<vault>'` (migration 0011 ships it `NOLOGIN`). | [ops] |
| 1.3 | Point the scoped client at it | Set `APP_DATABASE_URL` (authmatic_app) + `ADMIN_DATABASE_URL` (privileged) — ticket 0034. | [ops] |
| 1.4 | Migrate PHI reads/writes to `.query()` | Move remaining InsForge-SDK queries onto `getInsForgeClient(session).query()` so RLS is the **enforced** path, not just app-layer checks (ADR 0007). `submissions.ts` direct-pg path already done. | [code] |
| 1.5 | Backups + restore drill | Verify InsForge backup retention in the BAA; schedule nightly `pg_dump`; run the **first quarterly restore drill** (ADR 0011). | [ops] |

## Phase 2 — Compliance / PHI (before any real patient data)

| # | Item | How | Owner |
|---|------|-----|-------|
| 2.1 | Sign BAAs | InsForge, OpenRouter (or self-host the planner model), Rtrvr, Daytona, Tigris, Opsera, Render (ADR 0008 §6). No PHI flows to a subprocessor without one. | [legal] |
| 2.2 | Tigris encryption + versioning | Enable SSE-KMS + bucket versioning; verify with `aws s3api get-bucket-encryption/get-bucket-versioning` against the Tigris endpoint (ADR 0008). | [ops] |
| 2.3 | Appoint Privacy Officer | Owns the breach-determination; store the breach-notice template in `docs/templates/` (runbook §6). | [legal] |
| 2.4 | AV scanning of uploads | Stand up ClamAV sidecar (or managed scanner); wire into `read_pdf_upload` (ADR 0010). | [ops] |

## Phase 3 — Deploy & runtime

| # | Item | How | Owner |
|---|------|-----|-------|
| 3.1 | Deploy web + agent | `infra/render.yaml` + the per-service Dockerfiles (ticket 0020). | [ops] |
| 3.2 | **Deploy the worker** | Run `python -m src.worker` as a Render **background worker** (separate dyno) — without it, enqueued runs never execute (ADR 0014). | [ops] |
| 3.3 | Flip to the canonical agent | `USE_PYTHON_AGENT=true`; point `AGENT_BASE_URL` at the agent service (ticket 0025). | [ops] |
| 3.4 | Health checks | Wire Render to `/readyz` (traffic gate) + `/healthz` (restart) for both services (ticket 0015). | [ops] |

## Phase 4 — Observability

| # | Item | How | Owner |
|---|------|-----|-------|
| 4.1 | Sentry | Install `@sentry/nextjs` + `sentry-sdk`; set `SENTRY_DSN`; configure sample rate + `beforeSend` PII scrub; upload source maps; throw a test error and confirm it lands redacted (ADR 0009). | [ops] |
| 4.2 | Distributed tracing | Add an OTLP exporter + backend (Honeycomb / Tempo / Datadog). The `X-Request-ID`/`traceparent` seam + per-verb timings are already in place (docs/observability.md, ticket 0021). | [ops]/[code] |
| 4.3 | Alerting / on-call | PagerDuty rotation + escalation policy; alert on `jobs.status='dead'` and `/readyz` failures (ADR 0011). | [ops] |

## Phase 5 — CI & dependencies

| # | Item | How | Owner |
|---|------|-----|-------|
| 5.1 | Branch protection on `main` | GitHub Settings → Branches: require green CI (`web`, `agent`, `migrations`, `secret-scan`) + 1 review (docs/contributing.md). | [ops] |
| 5.2 | Python lockfile + audit | Adopt `pip-tools`/`uv` for a pinned agent lockfile; add `pip-audit` (ticket 0033). | [code] |
| 5.3 | Re-audit deps | `pnpm audit --prod` (1 accepted build-time postcss advisory) + `pip-audit`; flip CI audits to blocking once clean. | [ops] |

---

## Code follow-ups (no infra needed — can be done now)

These are the only remaining **code** items; they don't need production access:

- **[1.4]** Migrate the rest of the PHI queries to the scoped `.query()` client (RLS-as-primary-control).
- **Run visibility:** the dashboard "recent runs" + Security log read web in-memory run state, so runs executed via the Python-agent path don't appear. Add an agent "list runs by clinic" endpoint and have those views read from it (observed during browser testing).
- **[0025] finalize:** `agent-orchestrator.ts` has been deleted; `USE_PYTHON_AGENT` is default-on. Remaining: add the both-services end-to-end integration test.
- **Status enum:** consider a shared single source of truth for `PaStatus` between the DB CHECK and the TS type (ticket 0036 reconciled them; a generator would prevent future drift).

## Verified locally (so you know the baseline works)

Against a real Postgres + the live agent, browser-tested end-to-end: auth
(login/401/httpOnly/rotation), rate limiting (429), idempotency (replay/422),
portal submit→adjudication→approved (durable), and the full agent run
(upload→proxy→worker→SSE→submitted, PHI cleared). Migrations 0001–0012 apply
clean; RLS provably blocks cross-tenant reads; web 40 + agent 27 tests green.
