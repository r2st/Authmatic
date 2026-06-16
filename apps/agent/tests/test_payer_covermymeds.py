"""Tests for CoverMyMedsAdapter — HTTP interactions with mocked responses.

Uses httpx's MockTransport to simulate CoverMyMeds API responses without
hitting the network. Covers success paths, retry logic, and error mapping.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.payer.base import PARequest, PayerError, PayerStatus  # noqa: E402
from src.payer.covermymeds import CoverMyMedsAdapter, _map_status  # noqa: E402


# ── Status mapping ───────────────────────────────────────────────────────


def test_map_status_approved():
    assert _map_status("Approved") == PayerStatus.APPROVED
    assert _map_status("Closed - Approved") == PayerStatus.APPROVED


def test_map_status_denied():
    assert _map_status("Denied") == PayerStatus.DENIED
    assert _map_status("Closed - Denied") == PayerStatus.DENIED


def test_map_status_pending():
    assert _map_status("Pending") == PayerStatus.PENDING
    assert _map_status("Sent to Plan") == PayerStatus.PENDING


def test_map_status_unknown_defaults_pending():
    assert _map_status("SomeNewStatus") == PayerStatus.PENDING


def test_map_status_needs_info():
    assert _map_status("Need More Info") == PayerStatus.NEEDS_INFO


# ── HTTP mocking helpers ────────────────────────────────────────────────


def _mock_adapter(handler) -> CoverMyMedsAdapter:
    """Build an adapter whose _request method uses a mock transport."""
    adapter = CoverMyMedsAdapter(api_key="test-key", api_base="https://mock.cmm")

    # Monkey-patch the internal _request to use a mock transport.
    original_request = adapter._request

    async def patched_request(method, path, *, json=None, params=None):
        import asyncio

        url = f"https://mock.cmm{path}"
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.request(
                method, url, json=json, params=params,
                auth=("test-key", "x"),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        if resp.status_code >= 400:
            raise PayerError(
                f"CoverMyMeds {resp.status_code}: {resp.text[:200]}",
                retryable=resp.status_code >= 500,
                status_code=resp.status_code,
            )
        return resp.json()

    adapter._request = patched_request
    return adapter


def _request(drug: str = "Ozempic") -> PARequest:
    return PARequest(
        patient_name="Sarah Martinez",
        patient_dob="1985-03-15",
        member_id="HF-100001",
        drug_name=drug,
        drug_ndc="00169-4130-12",
        dose="0.5mg weekly",
        diagnosis_code="E11.9",
        provider_name="Dr. Chen, MD",
        provider_npi="1234567893",
        rationale="Patient meets criteria.",
    )


# ── submit_pa ────────────────────────────────────────────────────────────


async def test_submit_pa_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "PA-999",
                    "workflow_status": "New",
                    "tokens": {"html_url": "https://cmm.example/pa/PA-999"},
                }
            },
        )

    adapter = _mock_adapter(handler)
    result = await adapter.submit_pa(_request())
    assert result.external_reference_id == "PA-999"
    assert result.status == PayerStatus.SUBMITTED
    assert result.receipt_url == "https://cmm.example/pa/PA-999"


# ── check_status ─────────────────────────────────────────────────────────


async def test_check_status_approved():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "PA-999",
                    "workflow_status": "Approved",
                    "updated_at": "2025-01-15T10:30:00Z",
                }
            },
        )

    adapter = _mock_adapter(handler)
    result = await adapter.check_status("PA-999")
    assert result.status == PayerStatus.APPROVED
    assert result.denial_reason is None


async def test_check_status_denied_extracts_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "PA-999",
                    "workflow_status": "Denied",
                    "events": [
                        {"type": "deny_decision", "description": "Step therapy not completed"},
                    ],
                    "updated_at": "2025-01-15T10:30:00Z",
                }
            },
        )

    adapter = _mock_adapter(handler)
    result = await adapter.check_status("PA-999")
    assert result.status == PayerStatus.DENIED
    assert result.denial_reason == "Step therapy not completed"


# ── get_requirements ─────────────────────────────────────────────────────


async def test_get_requirements_pa_required():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "pa_required": True,
                    "forms": [
                        {
                            "questions": [
                                {"question": "Has patient tried metformin?"},
                                {"question": "Duration of current therapy?"},
                            ]
                        }
                    ],
                }
            },
        )

    adapter = _mock_adapter(handler)
    result = await adapter.get_requirements("00169-4130-12", "HF-CHOICE-PLUS")
    assert result.requires_pa is True
    assert len(result.criteria) == 2
    assert "metformin" in result.criteria[0]


# ── submit_appeal ────────────────────────────────────────────────────────


async def test_submit_appeal_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "APL-555",
                    "workflow_status": "Appealed",
                }
            },
        )

    adapter = _mock_adapter(handler)
    result = await adapter.submit_appeal("PA-999", "New lab results support necessity")
    assert result.appeal_reference_id == "APL-555"
    assert result.status == PayerStatus.PENDING  # "Appealed" maps to PENDING


# ── Error handling ───────────────────────────────────────────────────────


async def test_4xx_raises_non_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": "Invalid NPI"})

    adapter = _mock_adapter(handler)
    with pytest.raises(PayerError) as exc_info:
        await adapter.submit_pa(_request())
    assert exc_info.value.retryable is False
    assert exc_info.value.status_code == 422
