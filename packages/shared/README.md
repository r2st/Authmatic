# @authmatic/shared

TypeScript types and constants shared across Authmatic's TS packages —
today that's `apps/web`, and any future TS consumer.

## In scope

- **Wire shapes for the `clinic_form` subdomain** (per
  [ADR 0005](../../docs/decisions/0005-data-model-boundary.md)). Today:
  `PaSubmissionRow` (DB row), `PaSubmission` (app-facing), `PaStatus`,
  `PaFormPayload`, `AdjudicationResult`, plus the `FORM_FIELDS` and
  `STATUS_LABELS` constants.
- Types that cross a process boundary (HTTP / SSE / DB) and need to
  stay in sync between producer and consumer.
- Pure value-object types (e.g. ICD-10 / NDC) once a second consumer
  appears.

## Out of scope

- **The `agent_run` subdomain** (`patients`, `prior_auths`,
  `agent_events`, `pa_embeddings`, `compliance_scans`). The agent owns
  these in Python (`apps/agent/src/persist.py`); there's no TS consumer
  yet. Add a TS wire type here only when one appears.
- React components, hooks, or anything UI-shaped.
- Runtime validation (zod, valibot). Add a peer package if/when needed.
- Anything used by only one app — keep it local until a second
  consumer needs it.

## Layout

```
packages/shared/
├── src/
│   ├── index.ts            Re-exports everything below.
│   └── pa-submission.ts    Clinic-form subdomain types + constants.
└── README.md               This file.
```

## Consuming

```ts
// apps/web/src/lib/submissions.ts
import type { PaSubmissionRow, PaSubmission } from "@authmatic/shared";
```

The package ships TypeScript source directly (no build step). Next.js
transpiles it via `transpilePackages` in `apps/web/next.config.ts`.
