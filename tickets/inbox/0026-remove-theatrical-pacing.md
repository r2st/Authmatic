---
id: 0026
title: Remove theatrical sleep() pacing from the production request path
area: web
priority: P1
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: [0025]
---

## Goal

`apps/web/src/lib/agent-orchestrator.ts` injects artificial delays into
the live run path purely for demo feel: `emitStep(..., 800)`,
`400`, `600`, `700`, `500`, a hardcoded `reviewMs = 600`, and a 4s
`Promise.race` fallback for Rtrvr. Comments openly call it "theatrical
pacing" and "dead time". In production this slows every real run by
several seconds for no functional reason and couples UX timing to
business logic.

## Acceptance criteria

- [ ] All `sleep()` / `setTimeout` delays whose only purpose is pacing are removed from the server pipeline
- [ ] `emitStep`'s `minMs` parameter deleted; steps emit as soon as the underlying work completes
- [ ] Any desired progressive-disclosure animation moves to the client (CSS/React transitions on SSE events), not the server
- [ ] The Rtrvr timeout becomes a real, configurable operation timeout (not a fixed 4s demo race) with the value justified
- [ ] A real run's wall-clock is bounded by actual sponsor latency, measured and logged ([[0011]])

## Files / surfaces

- `apps/web/src/lib/agent-orchestrator.ts`
- `apps/web/src/app/run/[id]/page.tsx` (client-side animation, if added)

## Notes

> **Decision update (2026-06-03):** the canonical agent is the Python ReAct loop (apps/agent/) per ADR 0013 (ticket 0025). This ticket targets that agent, not the scripted agent-orchestrator.ts.

Depends on [[0025]] — if the Python agent becomes canonical, this file
may be deleted entirely and the ticket folds into that work. Kept
separate because the same "remove fake delays" rule applies wherever
the canonical agent lives.

## Log

## Outcome
