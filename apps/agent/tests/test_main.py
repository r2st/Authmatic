"""API-layer tests for the agent service (ticket 0010).

Covers /api/run input validation (400 non-PDF, 413 oversize) and that the
service token is required (401 without it). The DB pool + agent run are not
exercised here — validation happens before either is touched, and the
service-token dependency is overridden only for the validation cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from src.auth import require_service_token  # noqa: E402
from src.upload import MAX_PDF_BYTES  # noqa: E402


@pytest.fixture
def client_authed():
    """TestClient with the service-token dependency satisfied."""
    main.app.dependency_overrides[require_service_token] = lambda: None
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def test_run_requires_service_token():
    # No override → AGENT_SERVICE_TOKEN unset in dev means the dep allows, so
    # force prod-like by setting an expected token and sending none.
    import os

    os.environ["AGENT_SERVICE_TOKEN"] = "expected"
    try:
        with TestClient(main.app) as c:
            r = c.post("/api/run", files={"pdf": ("x.pdf", b"%PDF-1.4 ok", "application/pdf")})
        assert r.status_code == 401
    finally:
        del os.environ["AGENT_SERVICE_TOKEN"]


def test_run_rejects_non_pdf(client_authed):
    r = client_authed.post(
        "/api/run", files={"pdf": ("x.exe", b"MZ\x90\x00 not a pdf", "application/pdf")}
    )
    assert r.status_code == 400


def test_run_rejects_oversize(client_authed):
    big = b"%PDF-1.4\n" + b"x" * (MAX_PDF_BYTES + 10)
    r = client_authed.post("/api/run", files={"pdf": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_healthz_is_public():
    with TestClient(main.app) as c:
        r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
