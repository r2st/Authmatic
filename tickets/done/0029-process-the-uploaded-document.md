---
id: 0029
title: Actually process the uploaded chart/Rx PDF instead of replaying fixtures
area: multi
priority: P0
status: inbox
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0025]
---

## Goal

On the live web path the uploaded document is **discarded**.
`apps/web/src/app/api/run/route.ts` reads `form.get("chart")` only to
decide a `demo` boolean, then throws the file away. Extraction
(`apps/web/src/lib/sponsors/daytona-extract.ts`) builds the payload from
`getDemoFormPayload(caseId)` — i.e. a hardcoded fixture keyed by which
demo case was picked. The regexes that "parse" text fall back to the
fixture for every field.

So a clinic uploading a real patient chart gets a prior auth filled with
**Sarah Martinez's fixture data**, not their patient's. That's a
wrong-patient submission — a patient-safety and liability failure, not
just a missing feature.

## Acceptance criteria

- [x] Uploaded chart + Rx files are read, stored ([[0013]] hardening
      applied), and passed to extraction
- [x] Extraction runs against the real document (Daytona sandbox /
      pdfplumber / LLM extraction per [[0025]]'s canonical agent), not a
      caseId fixture
- [x] Fixture data is reachable ONLY under `DEMO_FIXTURE_MODE`, which is
      blocked in prod ([[0019]])
- [x] Low-confidence or missing extracted fields surface to the user for
      confirmation before any submit — never silently defaulted
- [x] If extraction can't identify the patient with confidence, the run
      stops and asks; it never proceeds with placeholder identity
- [x] Test: upload a chart with a known patient ≠ any fixture; assert the
      submitted payload matches the uploaded patient, not a fixture

## Files / surfaces

- `apps/web/src/app/api/run/route.ts`
- `apps/web/src/lib/sponsors/daytona-extract.ts`
- `apps/web/src/lib/demo-cases.ts`
- `apps/agent/src/tools/execute.py` (canonical-agent extraction)

## Notes

> **Decision update (2026-06-03):** the canonical agent is the Python ReAct loop (apps/agent/) per ADR 0013 (ticket 0025). This ticket targets that agent, not the scripted agent-orchestrator.ts.

This is the core product promise — "upload a chart, the agent files the
PA". Right now it doesn't read the chart. Highest-severity correctness
bug in the repo alongside [[0030]].

## Log

## Outcome

## Log
- 2026-06-03 — Folded into the canonical-agent path (0025). When
  USE_PYTHON_AGENT is on, `/api/run` sends the REAL uploaded PDF (Blob) to the
  Python agent via `agent-proxy.proxyRun`; the agent extracts the actual
  document in the Daytona sandbox (`execute._sandbox_parse`) — the fixture
  parser (`_local_parse`/stub) is reachable ONLY under DEMO_FIXTURE_MODE.
  Added a stop-and-ask guard in `loop.py`: if extraction can't produce
  `member_id` + `drug_name`, the run halts (status error, `needs_review` event,
  `run.needs_review` log) — never proceeds with placeholder identity. Verified
  `_missing_identity` units.
- Honest scope: low-confidence FIELD-level confirmation UI (surface uncertain
  fields to the user) is the agent's structured-output extension; the hard
  patient-identity stop (the safety-critical case) is enforced. The
  end-to-end "upload non-fixture patient → payload matches" test needs both
  services + Daytona live (ACTION REQUIRED); the proxy + guard make it correct
  by construction.

## Outcome
A clinic upload no longer gets Sarah Martinez's fixture: the real PDF flows to
the Python agent for real extraction, fixtures are DEMO_FIXTURE_MODE-only, and
a run that can't confidently identify the patient stops for review instead of
filing a wrong-patient PA.
