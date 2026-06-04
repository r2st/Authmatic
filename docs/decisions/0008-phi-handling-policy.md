# ADR 0008 — PHI handling policy

- **Status:** accepted
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0008-phi-handling-policy.md
- **Regulatory basis:** HIPAA Security Rule §164.312 (access control, audit, integrity, transmission security); Privacy Rule §164.502(b) (minimum necessary); Breach Notification §164.404–410.
- **Related:** [ADR 0005 data-model boundary](0005-data-model-boundary.md), tickets 0011 (logging), 0014 (prompt injection), 0006 (RLS), 0023 (secrets).

Authmatic processes Protected Health Information. This ADR is the single
source of truth for what PHI we hold, where it may go, and how it is
protected. Every logging, storage, and LLM-prompt decision must comply.

## 1. What is PHI in our schema

Field-level classification. "Direct" = identifies the individual on its
own or with trivial effort; "Clinical" = health data, PHI in context.

| Field | Table(s) | Class | Handling |
|---|---|---|---|
| `patient_name` / `full_name` | pa_submissions, patients | Direct | Redact to initials in logs; never to LLM |
| `dob` | pa_submissions, patients | Direct | Mask in logs; never to LLM |
| `member_id` / `primary_patient_id` | pa_submissions, patients | Direct | Mask (keep last 4) in logs; never to LLM raw |
| `patient_ssn` | (parsed from PDF only) | Direct | Never stored, never logged, never to LLM; flagged by VERIFY |
| `diagnosis` / `diagnosis_code` / `icd10` | pa_submissions, prior_auths | Clinical | Code may appear in logs/LLM (needed for coverage logic); free-text diagnosis redacted |
| `medication` / `drug_name` / `drug_ndc` / `dose` | pa_submissions, prior_auths | Clinical | Permitted in logs + LLM (required for the workflow) |
| `justification` / `rationale` | pa_submissions, prior_auths | Clinical (free text) | Redact in logs; rationale may go to LLM only as model *output*, not echoed raw into shared history |
| `provider_name` | pa_submissions | Indirect | Permitted in logs |
| chart PDF bytes | Tigris `charts/` | Direct + Clinical | Encrypted at rest; key is `charts/{clinic_id}/{run_id}/{file}` (ticket 0013) |
| `reference_id` | pa_submissions | Identifier | Unguessable (ticket 0007); safe to log |

## 2. Logging rules

Enforced in code by `apps/web/src/lib/phi.ts` and `apps/agent/src/phi.py`
(`redact` / `redactPhi` / `redact_phi`). The structured loggers (ticket
0011) wrap these so log lines are redacted by construction.

| Level | May contain | Must NOT contain |
|---|---|---|
| INFO | reference_id, run_id, clinic_id, drug_ndc, icd10 code, status, timings | any Direct PHI, free-text clinical fields |
| WARN | same as INFO + error category | raw PHI |
| ERROR | same + stack trace + masked identifiers (member_id last-4) | raw member_id/dob/name/ssn, raw justification/rationale |

Rule: **never** pass a raw submission/patient record to a logger. Pass
`redactPhi(record)`. No `console.log`/`print` of PHI — replaced or removed
(ticket 0011 completes the sweep).

## 3. What may go to the planner LLM (OpenRouter / InsForge AI gateway)

The planner runs on a third-party model. Minimum-necessary applies.

- **Permitted in the prompt/history:** the verb-selection reasoning,
  drug_name, drug_ndc, dose, icd10 code, coverage-rule text, masked
  identifiers.
- **Prohibited raw:** member_id, patient_name, dob, ssn, free-text
  justification.
- **Enforcement:** `apps/agent/src/loop.py` now routes every tool result
  through `_safe_for_history()` → `redact_phi()` before it re-enters the
  planner history. The raw `parsed` dict stays server-side and is used
  only to fill the actual payer form (not sent to the LLM). This also
  blunts prompt injection (ticket 0014) by stripping attacker free text
  from what the planner sees.
- **Code-review finding (this ticket):** before the fix, the `EXECUTE`
  result (raw `parsed`, incl. member_id/patient_name) was appended to the
  shared history verbatim — i.e. sent to OpenRouter. Fixed.

## 4. Storage matrix

| Store | Holds | Encryption at rest | Notes |
|---|---|---|---|
| InsForge Postgres | structured PHI (all tables) | Provider-managed (verify in BAA) | RLS per clinic (ticket 0006) |
| Tigris (S3) `charts/` | chart PDFs | **SSE-KMS — must be enabled** | Versioning on; lifecycle per ticket 0022 |
| Ephemeral process memory | demo fallback Maps, agent queues | n/a (RAM) | Removed in prod (ticket 0016); never durable PHI |
| Logs / error reporter | redacted only | Provider-managed | PII scrubbing on (ticket 0011) |

**ACTION REQUIRED (human):** confirm Tigris bucket has SSE-KMS + versioning
enabled (`aws s3api get-bucket-encryption` / `get-bucket-versioning` against
the Tigris endpoint). Confirm InsForge encryption-at-rest terms in the BAA.

## 5. Audit log

`audit_log` table (db/migrations/0004_add_audit_log.sql) records who read
or mutated which resource, when, and whether it was allowed. Writes via
`apps/web/src/lib/audit.ts` (`auditLog`). Wired into `getSubmission` now;
full coverage (every `getRun`, adjudication, and cross-clinic `access_denied`
event) completes with the session/tenant work in tickets 0005 + 0006, which
supply actor identity. `detail` carries redacted context only — never raw
PHI.

## 6. BAA tracking

A Business Associate Agreement must be in place with every subprocessor
that can touch PHI before production launch.

| Subprocessor | Touches PHI? | BAA status |
|---|---|---|
| InsForge (Postgres/Storage) | Yes (all structured PHI) | **ACTION REQUIRED — obtain BAA** |
| OpenRouter / planner model provider | Yes (prompt; redacted per §3) | **ACTION REQUIRED — confirm BAA or self-host model** |
| Rtrvr.ai | Yes (fills payer form w/ PHI) | **ACTION REQUIRED** |
| Daytona | Yes (parses chart PDF) | **ACTION REQUIRED** |
| Tigris | Yes (stores chart PDFs) | **ACTION REQUIRED** |
| Opsera | Receives packet for PHI scan | **ACTION REQUIRED** |
| Render | Hosts services / logs | **ACTION REQUIRED** |

If a subprocessor will not sign a BAA, PHI must not flow to it (e.g. switch
the planner to a self-hosted/BAA-covered model).

## 7. Retention + right-to-delete

- **Retention:** PHI retained while a PA is active + 6 years (HIPAA
  documentation-retention floor, §164.316(b)(2)). Configure Tigris
  lifecycle + a scheduled DB purge per ticket 0022.
- **Right-to-delete:** a patient deletion request removes the
  `pa_submissions` / `patients` rows and the Tigris `charts/` objects for
  that patient, writes a `delete` audit row, and is irreversible. Procedure
  documented in the runbook (ticket 0022).

## Consequences

- Redaction helpers (`phi.ts`, `phi.py`) are the chokepoint; tickets 0011
  and 0014 build on them.
- The loop.py change reduces what the planner can do but does not change
  the demo path (the planner never needed raw identifiers).
- Several criteria are process/infra (BAAs, Tigris SSE, encryption terms) —
  tracked as ACTION REQUIRED items in this ADR and the ticket Log, not
  silently marked done.
