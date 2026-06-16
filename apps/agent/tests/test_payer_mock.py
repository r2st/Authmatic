"""Tests for MockPayerAdapter — the fixture-based payer integration.

Verifies that the mock adapter follows the PayerAdapter contract and
returns deterministic results for the demo drug set.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.payer.base import PARequest, PayerStatus  # noqa: E402
from src.payer.mock import MockPayerAdapter  # noqa: E402


def _request(drug: str = "Ozempic", member_id: str = "HF-100001") -> PARequest:
    return PARequest(
        patient_name="Sarah Martinez",
        patient_dob="1985-03-15",
        member_id=member_id,
        drug_name=drug,
        drug_ndc="00169-4130-12",
        dose="0.5mg weekly",
        diagnosis_code="E11.9",
        provider_name="Dr. Chen, MD",
        provider_npi="1234567893",
        rationale="Patient meets medical-necessity criteria.",
    )


async def test_submit_returns_pending_for_specialty_drug():
    adapter = MockPayerAdapter()
    result = await adapter.submit_pa(_request("Ozempic"))
    assert result.status == PayerStatus.PENDING
    assert result.external_reference_id.startswith("MOCK-")
    assert result.receipt_url is not None


async def test_submit_auto_approves_generic():
    adapter = MockPayerAdapter()
    result = await adapter.submit_pa(_request("Lisinopril"))
    assert result.status == PayerStatus.APPROVED


async def test_check_status_after_submit():
    adapter = MockPayerAdapter()
    submit = await adapter.submit_pa(_request())
    status = await adapter.check_status(submit.external_reference_id)
    assert status.external_reference_id == submit.external_reference_id
    assert status.status == submit.status


async def test_check_status_unknown_ref():
    adapter = MockPayerAdapter()
    status = await adapter.check_status("NONEXISTENT-REF-123")
    assert status.status == PayerStatus.PENDING


async def test_get_requirements_specialty():
    adapter = MockPayerAdapter()
    req = await adapter.get_requirements("00169-4130-12", "HF-CHOICE-PLUS")
    assert req.requires_pa is True
    assert len(req.criteria) > 0


async def test_get_requirements_generic():
    adapter = MockPayerAdapter()
    req = await adapter.get_requirements("00001-1234-56", "UHC-CHOICE-PLUS")
    assert req.requires_pa is False
    assert len(req.criteria) == 0


async def test_appeal_moves_to_pending():
    adapter = MockPayerAdapter()
    submit = await adapter.submit_pa(_request())
    appeal = await adapter.submit_appeal(submit.external_reference_id, "New clinical evidence")
    assert appeal.status == PayerStatus.PENDING
    assert appeal.appeal_reference_id.startswith("MOCK-APL-")
    # After appeal, status check should show pending.
    status = await adapter.check_status(submit.external_reference_id)
    assert status.status == PayerStatus.PENDING


async def test_submit_idempotency_different_refs():
    """Two submits for the same patient produce distinct external refs."""
    adapter = MockPayerAdapter()
    r1 = await adapter.submit_pa(_request())
    r2 = await adapter.submit_pa(_request())
    assert r1.external_reference_id != r2.external_reference_id
