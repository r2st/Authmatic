"""API-layer tests for the agent service (ticket 0010).

Covers /api/run input validation (400 non-PDF, 413 oversize) and that the
service token is required (401 without it), plus public /healthz.

We instantiate TestClient WITHOUT the context manager so the lifespan (which
opens a real asyncpg pool) does not run — every assertion here short-circuits
in the request handler before the DB pool is touched.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from src.auth import require_service_token  # noqa: E402
from src.upload import MAX_PDF_BYTES  # noqa: E402

client = TestClient(main.app)


def test_run_requires_service_token():
    os.environ["AGENT_SERVICE_TOKEN"] = "expected"
    try:
        r = client.post(
            "/api/run", files={"pdf": ("x.pdf", b"%PDF-1.4 ok", "application/pdf")}
        )
        assert r.status_code == 401
    finally:
        del os.environ["AGENT_SERVICE_TOKEN"]


def test_run_rejects_non_pdf():
    main.app.dependency_overrides[require_service_token] = lambda: None
    try:
        r = client.post(
            "/api/run", files={"pdf": ("x.exe", b"MZ\x90\x00 not a pdf", "application/pdf")}
        )
        assert r.status_code == 400
    finally:
        main.app.dependency_overrides.clear()


def test_run_rejects_oversize():
    main.app.dependency_overrides[require_service_token] = lambda: None
    try:
        big = b"%PDF-1.4\n" + b"x" * (MAX_PDF_BYTES + 10)
        r = client.post("/api/run", files={"pdf": ("big.pdf", big, "application/pdf")})
        assert r.status_code == 413
    finally:
        main.app.dependency_overrides.clear()


def test_healthz_is_public():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
