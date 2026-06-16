"""Tests for payer adapter selection and base types.

Verifies get_payer_adapter picks the right implementation based on
environment configuration, and that the dataclasses serialize correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.payer.base import (  # noqa: E402
    PARequest,
    PayerError,
    PayerStatus,
    SubmitResult,
    StatusResult,
    RequirementsResult,
    AppealResult,
)
from src.payer.mock import MockPayerAdapter  # noqa: E402
from src.payer.covermymeds import CoverMyMedsAdapter  # noqa: E402


# ── PayerStatus ──────────────────────────────────────────────────────────


def test_status_enum_values():
    assert PayerStatus.APPROVED == "approved"
    assert PayerStatus.DENIED == "denied"
    assert PayerStatus.PENDING == "pending"
    assert PayerStatus.NEEDS_INFO == "needs_info"


def test_status_in_set():
    terminal = {PayerStatus.APPROVED, PayerStatus.DENIED, PayerStatus.CANCELLED}
    assert PayerStatus.APPROVED in terminal
    assert PayerStatus.PENDING not in terminal


# ── Dataclasses ──────────────────────────────────────────────────────────


def test_submit_result_frozen():
    r = SubmitResult(
        external_reference_id="X-1",
        status=PayerStatus.SUBMITTED,
    )
    with pytest.raises(AttributeError):
        r.external_reference_id = "changed"


def test_pa_request_defaults():
    req = PARequest(
        patient_name="Test",
        patient_dob="2000-01-01",
        member_id="M-1",
        drug_name="Aspirin",
    )
    assert req.drug_ndc is None
    assert req.rationale is None


# ── PayerError ───────────────────────────────────────────────────────────


def test_payer_error_retryable():
    e = PayerError("timeout", retryable=True, status_code=503)
    assert e.retryable is True
    assert e.status_code == 503
    assert str(e) == "timeout"


def test_payer_error_not_retryable():
    e = PayerError("bad request", retryable=False, status_code=400)
    assert e.retryable is False


# ── Adapter selection ────────────────────────────────────────────────────


def test_get_payer_adapter_returns_mock_when_mock_payer_true():
    """When MOCK_PAYER=true, get_payer_adapter returns MockPayerAdapter."""
    from src.settings import Settings
    mock_settings = Settings(
        mock_payer=True,
        demo_fixture_mode=False,
        insforge_db_url="postgres://test:test@localhost/test",
    )
    with patch("src.payer.get_settings", return_value=mock_settings):
        from src.payer import get_payer_adapter
        adapter = get_payer_adapter()
        assert isinstance(adapter, MockPayerAdapter)


def test_get_payer_adapter_returns_mock_in_fixture_mode():
    """When demo_fixture_mode is on, always use mock regardless of mock_payer."""
    from src.settings import Settings
    mock_settings = Settings(
        mock_payer=False,
        demo_fixture_mode=True,
        insforge_db_url="postgres://test:test@localhost/test",
    )
    with patch("src.payer.get_settings", return_value=mock_settings):
        from src.payer import get_payer_adapter
        adapter = get_payer_adapter()
        assert isinstance(adapter, MockPayerAdapter)


def test_covermymeds_requires_api_key():
    """CoverMyMedsAdapter raises PayerError if api_key is empty."""
    with pytest.raises(PayerError):
        CoverMyMedsAdapter(api_key="")


def test_covermymeds_accepts_api_key():
    """CoverMyMedsAdapter initializes successfully with a key."""
    adapter = CoverMyMedsAdapter(api_key="test-key-123")
    assert adapter._api_key == "test-key-123"
