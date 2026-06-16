---
id: 0038
title: Rtrvr integration — execution needs a native bridge; Python agent's /agent payload is stale
area: agent
priority: P1
status: inbox
owner:
created: 2026-06-04
started:
closed:
depends_on: [0025]
---

## Goal

Verified live while attempting a real-agent test (Rtrvr → our deployed mock
portal). Two concrete blockers to the agent actually driving a browser:

### 1. Rtrvr execution requires a native bridge (not present here)
- `GET https://api.rtrvr.ai/health` → **200 healthy**, key valid. API + auth
  are fine.
- `POST /agent` (any URL, incl. `example.com`) → **HTTP 500**:
  `"Native bridge disconnected (port 9602)"` / `"Could not connect to native
  bridge after 20 attempts"`.
- So despite `RTRVR_MODE=cloud`, this account's `/agent` execution drives a
  browser through a **local Rtrvr extension/desktop bridge on port 9602**
  that must be installed + signed in. Without it, the agent cannot fill ANY
  page. This is an environment/setup requirement, not a code bug — but it
  must be documented + provisioned (CI/prod can't rely on a desktop bridge;
  needs Rtrvr's headless/cloud-exec option or a hosted bridge).

### 2. Python agent's Rtrvr request shape is stale
`apps/agent/src/tools/read_web.py:_agent_call` POSTs
`{task, schema, mode}`. The real Rtrvr API (confirmed via the web client
`apps/web/src/lib/sponsors/rtrvr-submit.ts`) expects
`{input, urls, response:{verbosity}}` and returns text to parse. So the
Python path would fail against real Rtrvr even with a bridge connected. The
web client is the correct reference.

## Acceptance criteria

- [ ] Document the Rtrvr bridge requirement (port 9602 / extension) in
      `docs/` + `.env.example`; decide the prod/CI execution model (hosted
      bridge vs cloud-exec) and record it
- [ ] `read_web._agent_call` updated to the real API contract
      (`input` / `urls` / `response.verbosity`) + response parsing, matching
      `rtrvr-submit.ts`
- [ ] With a bridge connected, a real run fills + submits **our mock portal**
      (`PA_PORTAL_URL`, defaults to the mock — never a payer) end-to-end
- [ ] `/api/smoke` rtrvr ping distinguishes "API healthy" from "bridge
      connected" so health checks don't falsely pass

## Files / surfaces

- `apps/agent/src/tools/read_web.py`
- `.env.example` (RTRVR_MODE + bridge note)
- `docs/` (Rtrvr setup)

## Notes

Footgun already fixed (this session): `read_web.py` no longer hardcodes the
UHC production portal — it targets `settings.pa_portal_url` (defaults to our
mock). Part of the [[0025]] agent build phase.

## Log

- 2026-06-04 (claude): findings verified live (Rtrvr health 200; /agent 500
  native-bridge); filed.

## Outcome
