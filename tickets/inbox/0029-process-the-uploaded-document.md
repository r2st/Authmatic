---
id: 0029
title: Actually process the uploaded chart/Rx PDF instead of replaying fixtures
area: multi
priority: P0
status: inbox
owner:
created: 2026-06-03
started:
closed:
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

- [ ] Uploaded chart + Rx files are read, stored ([[0013]] hardening
      applied), and passed to extraction
- [ ] Extraction runs against the real document (Daytona sandbox /
      pdfplumber / LLM extraction per [[0025]]'s canonical agent), not a
      caseId fixture
- [ ] Fixture data is reachable ONLY under `DEMO_FIXTURE_MODE`, which is
      blocked in prod ([[0019]])
- [ ] Low-confidence or missing extracted fields surface to the user for
      confirmation before any submit — never silently defaulted
- [ ] If extraction can't identify the patient with confidence, the run
      stops and asks; it never proceeds with placeholder identity
- [ ] Test: upload a chart with a known patient ≠ any fixture; assert the
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
