# ADR 0010 — PDF upload policy

- **Status:** accepted
- **Date:** 2026-06-03
- **Driver ticket:** tickets/done/0013-harden-agent-file-upload.md
- **Related:** [[0029]] (makes the web upload path actually flow into extraction), [ADR 0008 PHI](0008-phi-handling-policy.md)

## Context

The agent `POST /api/run` accepted any upload, read the whole body into
memory unbounded, trusted the client `content_type`, and used the raw
attacker-supplied filename in the storage key — a DoS, a MIME-spoof, and a
path-traversal vector in one handler.

## Decision

Enforced in `apps/agent/src/upload.py`, applied in `main.py:post_run`:

1. **Size cap — 20 MB.** Early reject on a declared `Content-Length`, then a
   hard streaming cap while reading in 1 MB chunks (don't trust the header
   alone). Oversize → `413`.
2. **Magic bytes.** Require a `%PDF-` prefix; a renamed `.exe` → `400`.
3. **Active-content rejection.** Reject PDFs containing `/JavaScript`, `/JS`,
   `/OpenAction`, `/AA`, `/Launch`, or `/EmbeddedFile`. A prescription PDF
   never needs executable actions; their presence signals a weaponized file →
   `400`. Verified zero false positives across the demo fixtures.
4. **Filename sanitization.** Strip path components, restrict to
   `[A-Za-z0-9._-]`, drop leading dots, cap 100 chars, never empty.
5. **Safe storage key.** `charts/{clinic_id}/{run_id}/{sanitized}` —
   uniqueness comes from clinic_id + run_id, never the untrusted filename.

## AV scanning — deferred, with a plan

Structural checks (above) stop the obvious cases but are **not** malware
detection. Full antivirus is **deferred**, not skipped:

- **Recommended:** ClamAV as a sidecar (or a managed scanner) that scans the
  bytes before they reach Daytona/storage. Quarantine on hit; audit the event.
- **Why deferred:** needs an infra component (sidecar + signature updates)
  that can't be provisioned/verified from here, and the chart PDF is already
  opened only inside the Daytona sandbox (isolation), which bounds blast
  radius in the interim.
- **ACTION REQUIRED (human):** stand up the scanner before processing
  untrusted real-world uploads at scale; wire it into `read_pdf_upload` as a
  post-validation step.

## Consequences

- The web upload path currently discards the file ([[0029]]); these guards
  bite once that path flows into extraction. Land [[0029]] with or before the
  web-side mirror of these checks.
- The active-content denylist is intentionally conservative; if a legitimate
  PDF is ever rejected, prefer a proper PDF sanitizer (e.g. re-rendering)
  over loosening the denylist.
