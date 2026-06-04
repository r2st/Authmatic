---
id: 0031
title: Remove hardcoded demo identity from the real submission payload
area: web
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

The form-fill path injects hardcoded demo values that would ride along
on a real payer submission:

- `apps/web/src/lib/portal-form-data.ts:68`: `prescriber_npi:
  "1234567890"` — a **fabricated NPI** on every submission.
- `apps/web/src/lib/sponsors/rtrvr-submit.ts`: falls back to
  `?? "Sarah"`, `?? "Martinez"`, `?? "Emily"`, and hardcodes
  `prescriber_last_name: Chen`, `prescriber_npi: 1234567890`.

Submitting a prior authorization to a real payer with a fake or
mismatched NPI is at best an instant denial and at worst fraud
(misrepresenting the prescriber). The prescriber identity must come from
verified provider records, never a literal.

## Acceptance criteria

- [x] Real submission path (`rtrvr-submit.ts`) carries no identity literal: patient from `fields`, prescriber from a required `Prescriber` arg. Demo-portal filler literals are now clearly DEMO-ONLY (simulated sandbox, never a real payer).
- [x] NPI validated (10 digits + Luhn over the `80840` prefix per CMS spec) in `lib/npi.ts`; invalid → reject. Verified `1234567893` valid, fabricated `1234567890` invalid.
- [x] `?? "Sarah"`/`"Martinez"`/`"Emily"`/`Chen` fallbacks removed from `rtrvr-submit.ts`; missing patient OR prescriber identity → `submitWithRtrvr` refuses (`used:false` + error), never fabricates. Demo name-literals removed.
- [x] `providers` table modeled (`0008_add_providers.sql`): clinic_id FK, name, NPI (format CHECK), taxonomy, RLS-scoped. `Prescriber` type added. **Wiring the caller to pull from it depends on [[0029]]** (blocked on [[0025]]); until then the path is fail-closed = required behavior.
- [x] grep for fabricated identity in the submission path returns only a comment + the test asserting rejection.
- [x] Test (`npi.test.ts`, vitest): no-provider → refused; invalid-NPI → refused; NPI validator units. **5 pass.**

## Files / surfaces

- `apps/web/src/lib/portal-form-data.ts`
- `apps/web/src/lib/sponsors/rtrvr-submit.ts`
- `apps/web/src/lib/demo-cases.ts`
- `db/migrations/000X_add_providers.sql` (new)

## Notes

Pairs with [[0029]] (uploads discarded) and [[0030]] (fake
adjudication) — together they're the "demo fakes the clinical data"
cluster. All three must be closed before this can touch a real payer.

## Log

## Outcome

## Log

- 2026-06-03 — Closed the real-payer fraud risk: `lib/npi.ts` (Luhn/NPI
  validation), `Prescriber` type + required-and-validated identity in
  `submitWithRtrvr` (fail-closed refusal, no literal fallbacks),
  `0008_add_providers.sql` (RLS-scoped provider records). Demo-portal
  filler (`getDemoPortalFormValues`) keeps simulated-sandbox values but
  with name-literals removed and a Luhn-valid demo NPI, clearly marked
  DEMO-ONLY. 5 vitest tests pass; typecheck clean.
- Caller wiring (orchestrator pulling a provider record) depends on
  [[0029]] (real document processing, blocked on [[0025]]) — the
  fail-closed refusal is the correct interim behavior the ticket asks
  for. Did not edit `agent-orchestrator.ts` (other agent's hot file);
  `submitWithRtrvr(formPayload)` still compiles and now fails closed on
  the real path.

## Outcome

A real payer submission can no longer carry a fabricated NPI or
demo prescriber/patient identity. NPI is Luhn-validated; missing/invalid
identity is refused, never substituted. Provider records are modeled +
RLS-scoped. Pulling identity from those records is wired once [[0029]]
lands; the path is fail-closed until then.
