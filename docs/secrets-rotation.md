# Secrets management & rotation

> Draft (ticket 0023). Goal: no production secret lives in a committed
> file; every secret has an owner and a rotation cadence.

## Inventory

| Secret | Used by | Source (prod) | Cadence |
|--------|---------|---------------|---------|
| INSFORGE_API_KEY | web | Render secret group | 90d |
| INSFORGE_DB_URL | agent, scripts | Render secret group | on credential change |
| OPENROUTER_API_KEY | agent (planner) | Render secret group | 90d |
| DAYTONA_API_KEY | agent | Render secret group | 90d |
| RTRVR_API_KEY | agent, web | Render secret group | 90d |
| OPSERA_TOKEN | agent | Render secret group | 90d |
| TIGRIS_ACCESS_KEY_ID / SECRET | web | Render secret group | 90d |
| Session signing key (ticket 0005) | web | Render secret group | 180d |

## Rules

- `.env*` files are git-ignored; only `.env*.example` (no values) is
  committed. Verify history is clean: `gitleaks detect` over the full
  history (wired in CI per ticket 0009).
- Production secrets live in Render's secret groups (or a dedicated vault
  if we outgrow them — Doppler / Infisical / AWS Secrets Manager; decide
  in `docs/decisions/0012-secrets-management.md`).
- Rotation procedure: provision new → deploy → verify `/readyz` → revoke
  old. No overlap gap in which the service is keyless.

## On compromise

1. Revoke the leaked credential at the provider immediately.
2. Rotate, redeploy, verify.
3. Audit access logs for misuse during the exposure window.
4. If the credential could reach PHI, treat as a potential breach
   ([backups.md](backups.md)).
