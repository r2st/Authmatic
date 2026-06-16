---
id: 0037
title: Demo runs mint shifting reference IDs that never resolve (in-memory state not shared); status poller never gives up
area: web
priority: P0
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

Found by browser-testing the demo flow (login → New PA → run James Wilson)
in `DEMO_FIXTURE_MODE` (no InsForge). The run "completes" but the embedded
portal panel shows **"Reference ID not found"**, and the reference is
unstable.

**Verified, smoking gun:** reading the SAME run's `reference_id` twice
returned two DIFFERENT values (`PA-C1269FEE1EC2BE82` in the banner, then
`PA-234FEFD3ECD785B3` on re-read), and both `/api/pa/<ref>` → 404. The
iframe meanwhile showed a third ref (`PA-2A62…`). The reference changes on
every read and none resolve.

### Root cause: unreliable in-memory state ([[0016]], [[0028]])
With no InsForge configured, submissions + run state live in module-level
`Map`s (`submissions.ts memory`, `agent-runs.ts globalThis.__agentRuns`).
In the Next dev server this is NOT reliably shared across route modules,
AND `/api/stream/[id]` re-invokes `runAgentPipeline` whenever
`isPipelineRunning(id)` reads false — so each reconnect/poll RE-RUNS the
agent, each run calls `createSubmission` again and mints a NEW ref, and the
lookup routes can't see what was written. Net: every submission/receipt
lookup 404s. The whole persistence half of the offline demo is broken
without a real backend. This is exactly why 0016 (no silent in-memory
fallbacks) + 0028 (durable run/SSE state) are P0.

### Contributing defects:

### 1. Two submissions per run (divergent reference IDs)
The run creates a submission **twice**, via two independent paths:
- ~~`agent-orchestrator.ts:210`~~ (deleted) → `createSubmission(formPayload)` → ref shown
  in the run banner (e.g. `PA-C1269FEE1EC2BE82`). Now handled by the Python agent via `agent-proxy.ts`.
- the autofill iframe `PriorAuthForm.tsx:149` (`autofill=1`) → POST
  `/api/pa/submit` → a **second** `createSubmission` with a **different**
  ref (e.g. `PA-2A62CAE20DB73780`).

So one PA run produces two `pa_submissions` rows with two reference IDs.
The run banner shows one; the iframe's status view shows the other. This
is the concrete manifestation of the duplicate-submission risk in
[[0017]] (idempotency) — with real payers this is a double-filing.

### 2. Status poller never stops on 404
`apps/web/src/app/portal/healthfirst/submission/[ref]/page.tsx` polls
`GET /api/pa/${ref}` on a 2500ms `setInterval`; on 404 it sets
"Reference ID not found" but **keeps the interval running** — the server
log shows the 404 repeated indefinitely. No give-up, no backoff, no
clear-on-terminal.

## Acceptance criteria

- [ ] A single run produces exactly ONE submission / one reference ID;
      the run banner and the portal panel show the SAME ref
- [ ] The orchestrator and the autofill path share one submission (pass the
      run's reference into the autofill, or have the orchestrator not
      double-submit) — keyed by an idempotency key ([[0017]])
- [ ] The submission status poller stops after a terminal status OR after N
      failed attempts (e.g. 5), with backoff; no infinite 404 loop
- [ ] "Reference ID not found" only shows for a genuinely unknown ref, not
      a race against creation
- [ ] Browser re-test: run a PA, confirm the portal panel resolves to the
      run's own reference with no 404 storm

## Files / surfaces

- ~~`apps/web/src/lib/agent-orchestrator.ts`~~ (deleted; replaced by `apps/web/src/lib/agent-proxy.ts`)
- `apps/web/src/components/portal/PriorAuthForm.tsx`
- `apps/web/src/app/portal/healthfirst/submission/[ref]/page.tsx`
- `apps/web/src/app/run/[id]/page.tsx`
- `apps/web/src/app/api/pa/submit/route.ts`

## Notes

The orchestrator half is demo-only (ADR 0013); once [[0025]] routes runs
through the Python agent the double-submit may resolve differently — but
the **poller give-up bug (#2) is in the real portal component** and should
be fixed regardless. Verified live 2026-06-03; refs above are real from
that run.

## Log

## Outcome
