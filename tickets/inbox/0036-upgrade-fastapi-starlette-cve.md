---
id: 0036
title: Upgrade FastAPI + Starlette to clear GHSA-7f5h-v6xp-fcq8 (multipart DoS)
area: agent
priority: P1
status: inbox
owner:
created: 2026-06-03
started:
closed:
depends_on: []
---

## Goal

`starlette@0.46.2` (shipped in the agent via FastAPI) has
**GHSA-7f5h-v6xp-fcq8** — a multipart/form-data DoS. It's directly
relevant: `POST /api/run` accepts multipart PDF uploads. Fixed in
starlette 0.49.1.

This is the **only genuinely-shipped critical/high CVE** from the grype
triage (ticket 0033) — the other ~33 were the esbuild dev binary
(ignored via `.grype.yaml`, not in the prod image) and vitest (dev-only).

## Why it's not a one-line bump

FastAPI 0.115 pins `starlette<0.47.0`, so starlette can't move alone.
`pip` resolves the upgrade to **fastapi 0.115→0.136 + starlette 0.46→1.x**
(starlette crossed a major version). That can break:
- the agent's request/response handling and exception handlers,
- `sse-starlette` (pinned `<3`, depends on starlette) — the SSE stream
  on `/api/stream/{id}`,
- multipart handling in `read_pdf_upload` (ticket 0013).

So it must be done with the agent **runnable + integration-tested**, not
blind-applied.

## Acceptance criteria

- [ ] Bump `apps/agent/requirements.txt`: `fastapi` + `starlette>=0.49.1`
      (and `sse-starlette` to a starlette-1.x-compatible release)
- [ ] `pip install` resolves with no conflicts; `pip check` clean
- [ ] Agent imports + boots (`uvicorn main:app`) against a local DB
- [ ] `pytest apps/agent` green (incl. upload + any SSE tests)
- [ ] Manual smoke: upload a PDF → run → SSE stream → terminal status,
      against `make dev`
- [ ] `grype` shows the starlette High cleared
- [ ] Multipart size/limit behavior re-confirmed (0013 hardening intact)

## Files / surfaces

- `apps/agent/requirements.txt`
- `apps/agent/main.py` (exception handlers / app wiring if APIs changed)
- `apps/agent/src/upload.py` (multipart parsing)

## Notes

Needs the agent running (DB + services), so pair with the 0025 build
phase or do it on a branch with `make dev` up. Verify, don't guess —
starlette 0.x→1.x has real breaking changes.

## Log

## Outcome
