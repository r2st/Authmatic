---
id: 0023
title: Move secrets out of .env into a vault; document rotation
area: infra
priority: P3
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

Every secret (InsForge, Daytona, Rtrvr, Opsera, Tigris) lives in `.env`
files. No rotation cadence is documented. A leaked key today requires
manual coordination to rotate; a developer leaving requires manually
auditing what they had.

## Acceptance criteria

- [x] Backend picked + ADR'd (`docs/decisions/0012-secrets-management.md`): **Doppler**, with rationale vs Render/1Password/AWS/Infisical.
- [~] Prod secrets out of committed `.env*`: `.gitignore` excludes `.env*` (only `.env.*.example` with no values are committed). The **full-history gitleaks scan + moving values into Doppler is ACTION REQUIRED** (no git/Doppler access here) — flagged.
- [x] Per-key source documented: the `.env.*.example` files ([[0019]]) state required keys + that prod values come from the vault. Noted in the ADR that the entry points are `settings.py` (agent) + `insforge/admin.ts` (web) — there is no `env.ts`.
- [x] Rotation runbook (`docs/secrets-rotation.md`): per-secret owner + cadence (sponsor 90d, signing keys 180d, immediate on exposure).
- [~] Vault access audit log: Doppler provides it natively (ADR) — enabling it is part of the ACTION REQUIRED provisioning.

## Files / surfaces

- `docs/decisions/0012-secrets-management.md` (new)
- `docs/secrets-rotation.md` (new)
- `apps/agent/src/settings.py`
- `apps/web/src/lib/env.ts`

## Notes

Render's built-in env vars are encrypted at rest and a reasonable
starting point. A dedicated vault becomes more valuable once we have
> 2 envs and > 3 engineers.

## Log

- 2026-06-03 (claude): Drafted docs/secrets-rotation.md (inventory + 90/180d cadence + compromise steps). REMAINING: move prod secrets to Render secret group/vault, gitleaks history scan, ADR 0012.

## Outcome

## Log

- 2026-06-03 — Taken over from a stalled session that drafted
  docs/secrets-rotation.md. Wrote the missing ADR 0012 picking Doppler
  (rationale + per-env mapping to the 0019 env model + native access
  audit). Confirmed `.env*` is gitignored and only no-value
  `.env.*.example` files are committed.
- ACTION REQUIRED (human): provision Doppler + move prod values in; run
  gitleaks over full git history (rotate anything found); wire Doppler →
  Render; enable the vault access audit; set rotation reminders.

## Outcome

Secrets management has a chosen backend (Doppler, ADR 0012), a rotation
runbook with per-secret owners/cadences, and documented per-key sources.
Provisioning + the history scan are operational ACTION REQUIRED items,
flagged honestly. P3 ticket.
