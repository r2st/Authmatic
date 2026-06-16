# ADR 0005 — Data-model boundary between agent-run and clinic-form

- **Status:** accepted
- **Date:** 2026-06-03
- **Driver ticket:** [tickets/done/0002-adr-unify-or-document-split-data-model.md](../../tickets/done/0002-adr-unify-or-document-split-data-model.md)
- **Affects:** [db/migrations/0001_baseline.sql](../../db/migrations/0001_baseline.sql), [db/migrations/0002_add_pa_submissions.sql](../../db/migrations/0002_add_pa_submissions.sql), [db/migrations/0003_add_pa_submissions_review_cols.sql](../../db/migrations/0003_add_pa_submissions_review_cols.sql), [apps/agent/src/persist.py](../../apps/agent/src/persist.py), [apps/web/src/lib/submissions.ts](../../apps/web/src/lib/submissions.ts)

## a. Current state

Two disconnected slices of the schema co-exist, each driving a different demo surface:

**Agent-run subdomain** (baseline, `0001_baseline.sql`)
- `patients` — UUID PK, demographics + plan/member.
- `prior_auths` — UUID PK, one row per agent run (`run_id == prior_auths.id`). FK → `patients`. Status enum `pending|submitted|approved|denied|error`. Receipt URL, trigger PDF key, generated rationale.
- `agent_events` — UUID PK, one row per ReAct iteration. FK → `prior_auths`. Verb, plan, tool I/O, duration. `UNIQUE (pa_id, step_no)`.
- `pa_embeddings` — pgvector RAG over past approved rationales. Conditional on the `vector` extension.
- `compliance_scans` — Opsera VERIFY results, one per PA.
- Consumed by **`apps/agent/src/persist.py`** — drives `POST /api/run`, `GET /api/run/:id`, `GET /api/stream/:id`, and the `/run/:id` auditor page (the demo "money shot").

**Clinic-form subdomain** (added in `0002_add_pa_submissions.sql` + `0003_add_pa_submissions_review_cols.sql`)
- `pa_submissions` — `reference_id TEXT PRIMARY KEY` (e.g. `PA-2026-00451`). Fully denormalized: patient_name, dob, member_id, diagnosis, medication, dosage, provider_name, justification all inline. Status enum `pending_review|approved|denied|submitted`. Review-trail columns: `under_review_at`, `decided_at`, `decision_notes`, `denial_reason`, `reviewer_id`. JSONB `adjudication` payload.
- Consumed by **`apps/web/src/lib/submissions.ts`** — drives the HealthFirst clinic-portal sandbox at `apps/web/src/app/portal/healthfirst/*`. Provides `nextReferenceId / createSubmission / getSubmission / updateSubmission` with an in-memory fallback when InsForge isn't configured.

The two slices share no foreign key. They overlap conceptually (both are "a prior-authorization request") but were written for different stakeholders: the agent loop vs. a human-filled clinic form.

## b. Decision

**Keep split. Two named subdomains. One optional cross-link.**

- Subdomain **`agent_run`** owns `patients`, `prior_auths`, `agent_events`, `pa_embeddings`, `compliance_scans`. Stays as-is.
- Subdomain **`clinic_form`** owns `pa_submissions`. Stays as-is.
- A future migration MAY add `pa_submissions.agent_run_id UUID REFERENCES prior_auths(id) NULL` to allow an agent run to materialize a clinic-form row. Until that ticket lands, the two are disconnected.

No table is dropped. No column is migrated across the boundary. No application code changes are required by this ADR.

## c. Rationale

1. **They model different things.** `prior_auths` is the audit-first record of *what the autonomous agent did* (FK-normalized, append-only `agent_events` timeline). `pa_submissions` is the *human-filled clinic form*, denormalized so the HealthFirst portal can issue a `reference_id` and adjudicate without joins. Forcing both into one row would either denormalize the agent side (losing the patient FK and breaking RAG keyed on `patient_id`) or normalize the clinic side (forcing the portal to create a `patients` row before it has a member-id lookup, which it can't do for first-time submissions). Both regressions are worse than the current overlap.
2. **The PKs are intentionally different.** `prior_auths.id` is a UUID so the agent can mint it before the patient even exists. `pa_submissions.reference_id` is a human-visible `PA-2026-NNNNN` because the clinic UI prints it on the confirmation page and uses it as the URL slug for `/portal/healthfirst/submission/[ref]`. Neither PK is a good fit for the other surface.
3. **Unifying now is high-risk for the demo.** Each surface has working migrations, working code, and a working demo path. A unify pass would touch every method in both `persist.py` and `submissions.ts`, would force at least one breaking migration, and would invalidate the existing review-trail columns added in `0003`. Outside scope for a hackathon project that already ships both demos.
4. **A future link is cheap.** When (if) an agent run needs to materialize a clinic-form row, a nullable `agent_run_id` on `pa_submissions` is a one-line migration. Doing it now without a consumer is YAGNI.

## d. Consequences

- **`apps/agent/src/persist.py` stays authoritative for the agent-run subdomain.** Reads/writes `patients`, `prior_auths`, `agent_events`, `pa_embeddings`, `compliance_scans`. Does not touch `pa_submissions`.
- **`apps/web/src/lib/submissions.ts` stays authoritative for the clinic-form subdomain.** Reads/writes `pa_submissions`. Does not touch the agent-run tables.
- **Shared TS types stay narrow.** A `PASubmission` type in `packages/shared` (see ticket 0004) models the clinic-form row; an `AgentRun` / `RunEvent` type models the agent surface. They are not aliases of each other. This unblocks ticket 0004 against the web-side type only.
- **Migrations going forward** add to one subdomain or the other. A migration that touches both must reference this ADR and explain why.
- **New contributors:** if you're asking "should I add a column to `prior_auths` or `pa_submissions`?", the answer is whichever subdomain owns the surface you're building. If your work spans both, write a follow-up ADR that supersedes this one.
- **The optional cross-link** (`pa_submissions.agent_run_id`) is documented but not implemented. Track it as a future ticket when a consumer appears.

## Subdomain ownership map

| Table | Subdomain | Consumer file |
|---|---|---|
| `patients` | `agent_run` | `apps/agent/src/persist.py` |
| `prior_auths` | `agent_run` | `apps/agent/src/persist.py` |
| `agent_events` | `agent_run` | `apps/agent/src/persist.py` |
| `pa_embeddings` | `agent_run` | `apps/agent/src/persist.py` (conditional on pgvector) |
| `compliance_scans` | `agent_run` | `apps/agent/src/persist.py` |
| `pa_submissions` | `clinic_form` | `apps/web/src/lib/submissions.ts` |
