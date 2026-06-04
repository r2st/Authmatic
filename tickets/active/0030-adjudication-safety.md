---
id: 0030
title: Fix unsafe adjudication — default-approve and keyword-match decisions
area: web
priority: P0
status: active
owner: claude
created: 2026-06-03
started: 2026-06-03
closed:
depends_on: []
---

## Goal

Two clinical-safety defects in the decision path:

1. **Default-approve.** `apps/web/src/lib/agent-orchestrator.ts:218`:
   `const finalStatus = adjudication?.status ?? "approved";` — if
   adjudication returns null (submission not found, DB error, timeout),
   the run reports the PA as **approved**. A failure becomes a green
   light.

2. **Keyword-match "medical necessity."**
   `apps/web/src/lib/adjudication.ts` decides approve/deny by counting
   substring hits against a 21-word list (`STEP_THERAPY_KEYWORDS`,
   `checkStepTherapy` requires ≥2 hits) and a hardcoded formulary array.
   This is presented as payer medical review. As a real adjudication
   engine it is both trivially gameable (stuff keywords) and wrong
   (denies legitimate cases lacking the magic words).

If this is meant to simulate the *payer* (the HealthFirst mock portal),
it must be clearly walled off as a fixture and never run on real
submissions. If it's meant to be a real feature, it needs a real
clinical-rules engine and is out of scope for keyword matching.

## Acceptance criteria

- [x] `?? "approved"` removed; null/failed adjudication → `error` (or
      `needs_review`), never auto-approve. A failure must never present
      as an approval. — done in `agent-orchestrator.ts`; failed
      adjudication now throws → run status `error`, submission keeps real
      DB status.
- [x] Decide and document (`docs/decisions/0015-adjudication-scope.md`)
      whether adjudication is (a) the mock-payer simulation behind the
      demo portal only, or (b) a real product feature — decided **(a)**.
- [ ] If (a): `adjudication.ts` is gated to the HealthFirst mock portal
      and `DEMO_FIXTURE_MODE`; the real agent run reports "submitted /
      pending payer review" and does NOT fabricate a decision
      — REMAINING; depends on [[0019]] guard + [[0025]] (which agent is
      the real run path).
- [x] If (b): replaced with a real rules engine + human-in-the-loop;
      keyword matching deleted — N/A, chose (a).
- [ ] Hardcoded reviewer IDs (`HF-MCR-8842`, `HF-REV-DEMO`) removed from
      any real path; they belong only to the mock payer — REMAINING
      (folds into the gating above).
- [ ] No status transition to `approved`/`denied` happens without a
      recorded, auditable basis ([[0008]] audit log) — REMAINING;
      depends on [[0008]] audit log.

## Files / surfaces

- `apps/web/src/lib/agent-orchestrator.ts`
- `apps/web/src/lib/adjudication.ts`
- `apps/web/src/app/api/pa/[ref]/adjudicate/route.ts`
- `docs/decisions/0015-adjudication-scope.md` (new)

## Notes

A wrong "approved" on a prior auth can lead a clinic to dispense a drug
the payer won't cover, or skip an appeal that was warranted. Treat this
as patient-safety severity. Pairs with [[0029]] — both are "the demo
fakes the core clinical workflow."

## Log

- 2026-06-03 (claude): Fixed the P0 default-approve bug in
  `agent-orchestrator.ts:218` — a null adjudication now throws instead of
  reporting `approved`. Verified `tsc --noEmit` clean. Wrote ADR 0015
  deciding adjudication = mock-payer simulation. Remaining work (gating
  to `DEMO_FIXTURE_MODE`, removing hardcoded reviewer IDs from real
  paths, audit-logging transitions) is blocked on [[0019]], [[0025]],
  and [[0008]] respectively — left in `active/` until those land.

## Outcome
