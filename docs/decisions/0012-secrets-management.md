# ADR 0012 — Secrets management

- **Status:** accepted (backend chosen; migration + history scan are ACTION REQUIRED)
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0023-secrets-rotation-and-vault.md
- **Related:** [docs/secrets-rotation.md](../secrets-rotation.md), [ADR 0008 PHI](0008-phi-handling-policy.md), [ADR 0009 logging](0009-logging-and-error-reporting.md)

## Context

Every secret (InsForge, Daytona, Rtrvr, Opsera, Tigris, plus the new
`SESSION_SECRET` / `AGENT_SERVICE_TOKEN`) lives in `.env` files with no
rotation cadence and no access audit. A leaked key needs manual coordination
to rotate; an offboarding needs a manual audit of what someone held.

## Decision

**Backend: Doppler** (chosen over raw Render env vars, 1Password Secrets
Automation, AWS Secrets Manager, Infisical).
- Syncs secrets into Render (and local dev via `doppler run`) so secrets are
  never committed; per-environment configs (dev/staging/prod) map cleanly to
  the [[0019]] env model.
- Built-in access audit log (who read which secret when) — satisfies the
  audit criterion without building it ourselves.
- Lighter than AWS Secrets Manager for our scale; Infisical is a fine
  self-host alternative if vendor independence becomes a requirement.

**Secrets never in the repo.** `.env*` files are `.gitignore`d; only
`.env.*.example` (no values) are committed. Production values live in Doppler
and are injected at deploy.

**Per-key source documented.** The `.env.development/staging/production.example`
files ([[0019]]) state which keys are required per env and that prod values
come from the vault. `apps/agent/src/settings.py` reads from the env (Doppler-
injected); the web reads `process.env` (Doppler-injected). There is no
`apps/web/src/lib/env.ts`; `apps/web/src/lib/insforge/admin.ts` is the
documented env entry point.

**Rotation cadence** (detail in `docs/secrets-rotation.md`): sponsor creds
every 90 days; signing keys (`SESSION_SECRET`, `AGENT_SERVICE_TOKEN`) every
180 days; immediate rotation on suspected exposure. Each secret has a
`rotation_owner`.

## ACTION REQUIRED (human)

- Provision the Doppler project + per-env configs; move production secret
  values out of any `.env` into Doppler.
- Run `gitleaks` over the **full git history** to confirm no secret was ever
  committed; if one was, rotate it and scrub history.
- Wire Doppler → Render deploy; remove plaintext env from Render dashboards.
- Set rotation reminders per `secrets-rotation.md`.

## Consequences

- Secrets get a single source of truth + an access audit, and rotation
  becomes a documented routine instead of an ad-hoc scramble.
- The actual provisioning + history scan can't be done from here (no Doppler/
  git access) — tracked as ACTION REQUIRED, not silently closed.
