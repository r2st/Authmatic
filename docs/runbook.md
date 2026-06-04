# On-call runbook

> Draft (ticket 0022). PHI-regulated product — when in doubt, preserve
> data and escalate. Never delete to "fix" an incident.

## Severity

| Sev | Definition | Response |
|-----|------------|----------|
| SEV1 | PHI exposure, data loss, or PAs silently not filing | Page immediately, all-hands |
| SEV2 | Core flow down (uploads, runs, dashboard) | Page on-call, fix within hours |
| SEV3 | Degraded (one sponsor down, slow) | Next business day |

## Escalation

1. On-call engineer (rotation TBD — pick a tool per [ticket 0022]).
2. Eng lead.
3. Privacy officer — **mandatory for any suspected PHI exposure** (HIPAA
   breach-notification clock starts; see [backups.md](backups.md)).

## Playbooks

### `/api/readyz` returns 503
- Check which dep is `down` in the JSON body.
- InsForge down → check InsForge status; runs will fail loudly (no silent
  fallback after ticket 0016). Do not restart in a loop.
- Tigris down → uploads/receipts fail; PAs can still be recorded.

### A PA run is stuck in `running`
- After ticket 0027/0028, the queue marks stuck runs `failed` and retries.
- Until then: check agent logs by `run_id`; a dropped fire-and-forget run
  is the known cause. Re-submit with the same idempotency key (0017).

### Suspected prompt injection (agent did something wrong)
- Pull the run's planner I/O (logged per ticket 0014/0011).
- Disable live agent (`USE_PYTHON_AGENT=false`) to halt automated filing.
- Preserve logs; treat affected submissions as suspect.

### Sponsor outage (Rtrvr / Daytona / Opsera)
- Runs degrade per the agent's error handling; no auto-approve (ticket 0030).
- Communicate ETA; do not enable `DEMO_FIXTURE_MODE` in prod to "fix" it.

## Communication

- Status updates every 30 min during SEV1/2.
- Postmortem (blameless) within 5 business days of any SEV1/2.
