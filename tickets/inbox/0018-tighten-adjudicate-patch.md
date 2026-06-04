---
id: 0018
title: Replace arbitrary Partial<PaSubmission> patches with allowlist
area: web
priority: P2
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: [0005]
---

## Goal

`apps/web/src/lib/submissions.ts:updateSubmission` accepts
`patch: Partial<PaSubmission>` and passes every field straight to
`.update(patch)`. Callers can mutate any column: `status`,
`reviewer_id`, `submitted_at`, even change `member_id`. The
adjudicate route relies on convention to limit which fields move;
nothing enforces it.

## Acceptance criteria

- [ ] `updateSubmission` accepts a typed `PaSubmissionPatch` union — separate `MarkUnderReviewPatch`, `ApprovePatch`, `DenyPatch` shapes
- [ ] Allowlisted fields per action; any unexpected field rejected with 422
- [ ] Status transitions validated server-side (e.g. `denied → approved` requires explicit `reopen` action, not raw patch)
- [ ] `reviewer_id` always derived from session (depends [[0005]]), never accepted from caller
- [ ] `submitted_at` immutable after creation
- [ ] Tests assert each forbidden field returns 422

## Files / surfaces

- `apps/web/src/lib/submissions.ts`
- `apps/web/src/lib/adjudication.ts`
- `apps/web/src/app/api/pa/[ref]/adjudicate/route.ts`
- `packages/shared/src/pa-submission.ts` (depends [[0004]])

## Notes

Status-machine logic is a good candidate for a small state-machine lib
(xstate) once we have more transitions. Today's three transitions
(pending → under_review → approved|denied) don't justify it.

## Log

## Outcome
