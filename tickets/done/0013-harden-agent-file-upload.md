---
id: 0013
title: Harden agent PDF upload — size limit, MIME validation, filename sanitization
area: agent
priority: P1
status: done
owner: claude
created: 2026-06-03
started: 2026-06-03
closed: 2026-06-03
depends_on: []
---

## Goal

`apps/agent/main.py:67-72` accepts any `UploadFile`, reads the whole
body into memory with `await pdf.read()`, and uses the
attacker-supplied `pdf.filename` directly as part of the storage key
(`charts/{filename}`). This is three bugs:

1. **DoS via huge uploads** — no size cap, single request can OOM the worker.
2. **MIME check is trivially bypassed** — only checks `content_type` header (client-controlled), not magic bytes.
3. **Path traversal in storage key** — `filename = "../../etc/passwd"` becomes part of an InsForge storage key; behavior depends on InsForge's key handling but is at minimum a collision/poisoning vector.

## Acceptance criteria

- [x] 20 MB hard cap: early `Content-Length` reject + streaming guard while reading in 1 MB chunks (`read_pdf_upload`). Oversize → 413.
- [x] Magic-byte `%PDF-` check → 400 on a renamed non-PDF.
- [x] `sanitize_filename`: strips path separators, restricts to `[A-Za-z0-9._-]`, drops leading dots, caps 100 chars, never empty.
- [x] `storage_key()` → `charts/{clinic_id}/{run_id}/{sanitized}`; uniqueness from clinic_id+run_id. `create_run` inserts then sets the key (needs run_id).
- [x] Active-content rejection: `/JavaScript`, `/JS`, `/OpenAction`, `/AA`, `/Launch`, `/EmbeddedFile` → 400. (Verified zero false positives on demo fixtures.) Full "pdfplumber-can't-parse" rejection happens downstream in the Daytona parse step; structural denylist covers the JS-action case here.
- [x] AV scanning decision recorded in ADR `docs/decisions/0010-pdf-upload-policy.md` (deferred to a ClamAV sidecar / managed scanner; rationale + ACTION REQUIRED documented).
- [x] `apps/agent/tests/test_upload.py` — 10 tests (413 oversize ×2, 400 non-PDF, 400 traversal-safe key, 400 embedded-JS, 200 valid, sanitize cases). **All pass.**

## Files / surfaces

- `apps/agent/main.py`
- `apps/agent/src/upload.py` (new)
- `apps/agent/src/persist.py` (storage key derivation)
- `apps/agent/tests/test_upload.py` (new)
- `docs/decisions/0010-pdf-upload-policy.md` (new)

## Notes

The web app also has a chart-upload path (frontend) — verify whether
files traverse the web layer first (where similar checks should
mirror) or go straight to the agent.

Related to [[0029]]: today the web path *discards* the uploaded file
entirely, so these hardening checks have nowhere to bite on that path
yet. [[0029]] makes the upload actually flow into extraction; this
ticket ensures that flow is safe. Sequence [[0029]] first (or land them
together) so the hardening guards a real code path, not a dead one.

## Log

- 2026-06-03 — Added `apps/agent/src/upload.py` (`read_pdf_upload`,
  `sanitize_filename`, `storage_key`, active-content denylist). Wired
  into `main.py:post_run` (now also reads an optional `clinic_id` form
  field for the storage key) and restructured `persist.create_run` to
  insert-then-set a safe key. ADR 0010 written. 10 unit tests pass
  (`pytest tests/test_upload.py`). `main.py` imports clean.
- Partitioned work: agent-side only, no web hot-files touched (a
  concurrent agent owns the web tickets).
- Per ticket Notes: the web upload path discards files today ([[0029]]);
  these guards protect the agent intake. Web-side mirror lands with
  [[0029]].

## Outcome

Agent PDF intake hardened: 20 MB cap (header + streaming), `%PDF-`
magic-byte check, active-content (JS/OpenAction/EmbeddedFile) rejection,
filename sanitization, and a traversal-proof `charts/{clinic_id}/{run_id}/
{file}` storage key. AV scanning deferred with a documented plan (ADR
0010). 10 passing tests.
