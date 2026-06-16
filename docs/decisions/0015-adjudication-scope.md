# ADR 0015 — Adjudication is a mock payer, not a product feature

- **Status:** Accepted
- **Date:** 2026-06-03
- **Ticket:** [0030](../../tickets/active/0030-adjudication-safety.md)

## Context

`apps/web/src/lib/adjudication.ts` decides approve/deny by counting
substring hits against a 21-word `STEP_THERAPY_KEYWORDS` list and a
hardcoded formulary array, stamping hardcoded reviewer IDs
(`HF-MCR-8842`, `HF-REV-DEMO`). It is invoked inline from the agent run
(formerly `agent-orchestrator.ts`, now deleted; the Python agent in `apps/agent/` via `agent-proxy.ts`) as if it were a real payer decision.

Two defects made this dangerous:

1. `finalStatus = adjudication?.status ?? "approved"` — a null/failed
   adjudication was reported to the clinic as **approved**. A failure
   presented as a green light.
2. Keyword counting is not medical-necessity adjudication. It is
   trivially gamed and wrongly denies legitimate cases.

## Decision

- **Adjudication models the *payer* (HealthFirst), not Authmatic.** It
  is a demo/simulation of the insurer's medical-review queue so the
  end-to-end flow is visible. It is **not** a product feature Authmatic
  offers.
- **A failed or missing adjudication never yields `approved`.** The
  agent run errors; the submission keeps its real DB status
  (`pending_review` / `under_review`). Decisions are only ever the
  payer's recorded verdict. *(Implemented in this ticket.)*
- **The keyword engine is demo-grade and must be gated.** For any real
  deployment it runs only behind the HealthFirst mock portal and
  `DEMO_FIXTURE_MODE`; a real agent run reports "submitted — pending
  payer review" and fabricates no decision. *(Gating tracked as
  remaining work in [0030].)*
- **Hardcoded reviewer IDs belong only to the mock payer.** They must
  not appear on any real submission path.

## Consequences

- The clinic UI must handle "submitted, awaiting payer" as the terminal
  state of a real run — not an instant approve/deny.
- Real payer decisions arrive asynchronously (portal polling, payer
  webhook, or status-check); that ingestion is future work, separate
  from this demo simulator.
- If Authmatic ever offers pre-submission "will this be approved?"
  scoring, it is a distinct feature requiring a real clinical-rules
  engine + human-in-the-loop — explicitly out of scope here.
- Depends on [0019] for the `DEMO_FIXTURE_MODE` prod-refusal guard that
  makes the gating enforceable.
