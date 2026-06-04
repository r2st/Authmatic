---
id: 0004
title: Define first shared TS types in packages/shared
area: shared
priority: P2
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: [0002]
---

## Goal

`packages/shared` is an empty scaffold today. Move the type definitions
that both `apps/web` and (the TS surface of) `apps/agent` care about
into it, so changes flow from one source.

First candidates:
- `PASubmission` (the row shape returned by the agent / consumed by web dashboards)
- `RunEvent` (the SSE event payload streamed from agent → web)
- ICD-10 / NDC value-object types if any

## Acceptance criteria

- [x] `apps/web/src/lib/submissions.ts` `DbRow` aliased to `PaSubmissionRow` imported from `@authmatic/shared` (inline shape removed)
- [x] `apps/web/package.json` declares `@authmatic/shared` as `workspace:*`
- [x] `pnpm --filter authmatic-web build` passes (filter name per [[0001]])
- [x] Six additional shared types added: `PaStatus`, `PaSubmission`, `PaFormPayload`, `AdjudicationResult`, plus the `FORM_FIELDS` and `STATUS_LABELS` constants. `apps/web/src/lib/pa-types.ts` is now a thin re-export from `@authmatic/shared` so existing `@/lib/pa-types` consumers don't churn.
- [x] `packages/shared/README.md` written (in scope, out of scope, layout, consuming example)

## Files / surfaces

- `packages/shared/src/index.ts`
- `packages/shared/src/pa-submission.ts` (likely new)
- `packages/shared/README.md` (new)
- `packages/shared/package.json`
- `apps/web/package.json`
- `apps/web/src/lib/submissions.ts`

## Notes

Depends on [[0002]] only for the `PASubmission` shape — if the ADR
decides to unify the models, the type changes. If it stays split, this
ticket starts with the web-side type only.

## Log

- 2026-06-03 — Per ADR 0005, scope was the web-side `clinic_form`
  subdomain only. Moved `PaStatus`, `PaFormPayload`, `PaSubmission`,
  `AdjudicationResult`, `FORM_FIELDS`, `STATUS_LABELS` into
  `packages/shared/src/pa-submission.ts`. Added a new `PaSubmissionRow`
  type that mirrors the InsForge wire shape (nullable review-trail
  columns) so the consumer alias `type DbRow = PaSubmissionRow` is the
  one-liner the AC asked for.
- Touched 11+ consumers indirectly by making
  `apps/web/src/lib/pa-types.ts` a thin re-export from
  `@authmatic/shared` — avoided churning every `@/lib/pa-types` import
  in the codebase.
- Added `transpilePackages: ["@authmatic/shared"]` to
  `apps/web/next.config.ts` so Next.js compiles the TS-source workspace
  package (no build step in `packages/shared`).
- Verified: `pnpm install` clean, `pnpm --filter authmatic-web build`
  passes (lint + types + static pages).

## Outcome

`packages/shared` is no longer an empty scaffold. The `clinic_form`
subdomain types are exported from `@authmatic/shared` and consumed by
`apps/web` (directly in `submissions.ts`, via re-export everywhere else).
`PaSubmissionRow` is the new DB-row type; everything else moved
verbatim from `apps/web/src/lib/pa-types.ts`. Build green.
