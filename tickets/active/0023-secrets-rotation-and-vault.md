---
id: 0023
title: Move secrets out of .env into a vault; document rotation
area: infra
priority: P3
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

Every secret (InsForge, Daytona, Rtrvr, Opsera, Tigris) lives in `.env`
files. No rotation cadence is documented. A leaked key today requires
manual coordination to rotate; a developer leaving requires manually
auditing what they had.

## Acceptance criteria

- [ ] Secrets backend picked and ADR'd (`docs/decisions/0012-secrets-management.md`) — options: Render env vars + a Render-Secret-Sync, Doppler, 1Password Secrets Automation, AWS Secrets Manager, Infisical
- [ ] Production secrets removed from any `.env*` file checked into the repo (verify nothing committed historically — run `gitleaks` over history)
- [ ] `apps/agent/src/settings.py` and `apps/web/src/lib/env.ts` document expected source of each key per env
- [ ] Rotation runbook: each secret has a `last_rotated`, `rotation_owner`, `rotation_cadence` (sponsor-creds: every 90 days; signing keys: every 180 days)
- [ ] Audit log: who accessed which secret when (vault-level)

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
