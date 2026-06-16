---
id: 0008
title: Define and enforce a PHI handling policy across web, agent, LLM, storage
area: multi
priority: P0
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

This product handles PHI (name, DOB, member ID, diagnosis, medication,
clinical notes, chart PDFs). HIPAA and most BAAs require explicit
controls. Today the codebase has no written policy on what may be
logged, what may be sent to third-party LLMs, what gets stored in
Tigris vs InsForge, what gets redacted, or how access is audited.

Write the policy, then close every gap the audit surfaces.

## Acceptance criteria

- [x] `docs/decisions/0008-phi-handling-policy.md` written, covering all listed sub-points (field table, log levels, LLM redaction, storage matrix, encryption expectations, audit, retention + right-to-delete)
- [x] BAAs identified and tracked (§6 table) — each marked ACTION REQUIRED (human) since signing is a legal step
- [x] Code review of `loop.py` + `insforge_client.py`: found raw `parsed` (member_id, patient_name, ssn) was appended verbatim to the planner history → sent to OpenRouter. Fixed via `_safe_for_history()` → `redact_phi()`. Documented as a finding in ADR §3.
- [~] Audit-log table added (`0004_add_audit_log.sql`) + `auditLog()` helper; wired into `getSubmission`. Full coverage (every `getRun`, adjudicate, cross-clinic `access_denied`) needs actor identity from session → completes with [[0005]]/[[0006]]. Flagged, not fake-closed.
- [ ] **ACTION REQUIRED (human):** confirm Tigris SSE-KMS + versioning enabled (no API access from here)
- [x] No `console.*`/`print` of raw PHI introduced; redaction helpers (`phi.ts`/`phi.py`) in place. Full sweep of existing call sites completes in [[0011]] (logging) — only 4 console.* calls exist repo-wide and none log raw PHI today.

## Files / surfaces

- `docs/decisions/0008-phi-handling-policy.md` (new)
- `apps/web/src/lib/logging.ts` (new — redaction helpers)
- `apps/agent/src/logging.py` (new)
- `apps/agent/src/loop.py`
- `apps/agent/src/insforge_client.py`
- `db/migrations/000X_add_audit_log.sql` (new)

## Notes

Pairs with [[0011]] (structured logging — the redaction helpers land
there). Pairs with [[0017]] (prompt injection — same prompt edits).
HIPAA Security Rule §164.312 covers access control + audit. If we want
SOC 2 / HITRUST later, an audit log is table-stakes.

## Log

- 2026-06-03 — Wrote ADR 0008. Added redaction helpers
  `apps/web/src/lib/phi.ts` + `apps/agent/src/phi.py` (smoke-tested:
  member_id→`******2910`, name→`M.M.`, dob masked). Added
  `db/migrations/0004_add_audit_log.sql` + `apps/web/src/lib/audit.ts`,
  wired into `getSubmission`. Fixed a real PHI leak in `loop.py`: tool
  results (incl. raw member_id/name) were fed verbatim into the planner
  history sent to OpenRouter — now routed through `redact_phi()`.
- Deviation: the ticket Files list named `apps/web/src/lib/logging.ts`
  for the redaction helpers, but [[0011]] owns logging.ts. Put pure
  redaction in `phi.ts`/`phi.py`; 0011's logger will import them. Keeps
  one owner per file.
- ACTION REQUIRED (human), tracked in ADR: sign BAAs (InsForge,
  OpenRouter, Rtrvr, Daytona, Tigris, Opsera, Render); enable Tigris
  SSE-KMS + versioning; confirm InsForge encryption-at-rest in BAA.

## Outcome

PHI policy written and the highest-risk gap closed in code: the planner
LLM no longer receives raw identifiers (loop.py redaction). Redaction
helpers, an audit_log table + writer, and the audit wire-in on
`getSubmission` landed. Remaining criteria are legal/infra (BAAs, Tigris
SSE) or depend on session identity ([[0005]]/[[0006]]) — all flagged
honestly in the ADR and above, none fake-closed.
