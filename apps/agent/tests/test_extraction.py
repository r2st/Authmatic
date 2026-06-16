"""Tests for the LLM-based extraction pipeline.

Covers:
  - PDF text extraction (pdfplumber)
  - LLM response parsing and confidence assessment
  - Needs-review triggering on low-confidence critical fields
  - Error handling: empty PDF, missing API key, malformed LLM output
  - End-to-end parse_prescription with mocked LLM

Uses mocked httpx responses — no real LLM calls. Runs under plain pytest
without pytest-asyncio by using asyncio.run() for async functions.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.llm_extract import (  # noqa: E402
    CRITICAL_FIELDS,
    ExtractionResult,
    _assess_confidence,
    _parse_llm_response,
    extract_with_llm,
)
from src.tools.execute import (  # noqa: E402
    _extract_pdf_text,
    parse_prescription,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _good_llm_response() -> dict:
    """A well-formed LLM response with all critical fields at high confidence."""
    return {
        "fields": {
            "patient_name": {"value": "Sarah Martinez", "confidence": "high"},
            "dob": {"value": "1985-03-15", "confidence": "high"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "insurance_id": {"value": "GRP-44210", "confidence": "medium"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
            "drug_ndc": {"value": "00169-4130-12", "confidence": "high"},
            "dose": {"value": "0.5mg once weekly", "confidence": "high"},
            "icd10": {"value": "E11.9", "confidence": "high"},
            "icd_codes": {"value": ["E11.9", "E78.5"], "confidence": "medium"},
            "prescriber_name": {"value": "Dr. James Wilson", "confidence": "high"},
            "prescriber_npi": {"value": "1234567890", "confidence": "medium"},
            "diagnosis": {"value": "Type 2 diabetes mellitus", "confidence": "high"},
        }
    }


def _low_confidence_response() -> dict:
    """LLM response with low confidence on critical fields."""
    return {
        "fields": {
            "patient_name": {"value": "J. Smith", "confidence": "low"},
            "member_id": {"value": None, "confidence": "low"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
            "drug_ndc": {"value": "00169-4130-12", "confidence": "medium"},
            "dose": {"value": "unknown", "confidence": "low"},
            "icd10": {"value": "E11.9", "confidence": "medium"},
        }
    }


def _make_httpx_response(data: dict, status_code: int = 200):
    """Create a mock httpx response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(data)}}]
    }
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
    return mock_resp


def _mock_settings(**overrides):
    """Create a mock Settings with sensible defaults."""
    defaults = {
        "openrouter_api_key": "test-key-123",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "insforge_model": "meta-llama/llama-3.1-70b-instruct",
        "insforge_project_url": "https://authmatic.local",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ── _parse_llm_response tests ──────────────────────────────────────────

class TestParseLlmResponse:
    def test_parses_well_formed_response(self):
        resp = _good_llm_response()
        parsed = _parse_llm_response(json.dumps(resp))
        assert parsed["patient_name"]["value"] == "Sarah Martinez"
        assert parsed["patient_name"]["confidence"] == "high"
        assert parsed["drug_name"]["value"] == "Ozempic"

    def test_parses_flat_fields_without_wrapper(self):
        """LLM returns fields dict directly, not wrapped in {"fields": ...}."""
        flat = {
            "patient_name": {"value": "Jane Doe", "confidence": "high"},
            "drug_name": {"value": "Humira", "confidence": "medium"},
        }
        parsed = _parse_llm_response(json.dumps(flat))
        assert parsed["patient_name"]["value"] == "Jane Doe"
        assert parsed["drug_name"]["confidence"] == "medium"

    def test_parses_plain_values_without_confidence(self):
        """LLM returns plain values instead of {value, confidence} objects."""
        plain = {
            "fields": {
                "patient_name": "Jane Doe",
                "drug_name": "Humira",
            }
        }
        parsed = _parse_llm_response(json.dumps(plain))
        assert parsed["patient_name"]["value"] == "Jane Doe"
        # Default confidence is medium
        assert parsed["patient_name"]["confidence"] == "medium"

    def test_parses_json_from_markdown_code_block(self):
        """LLM wraps JSON in markdown code fences."""
        raw = '```json\n{"fields": {"drug_name": {"value": "Ozempic", "confidence": "high"}}}\n```'
        parsed = _parse_llm_response(raw)
        assert parsed["drug_name"]["value"] == "Ozempic"

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_llm_response("this is not json at all")

    def test_skips_underscore_prefixed_keys(self):
        resp = {
            "fields": {
                "drug_name": {"value": "Ozempic", "confidence": "high"},
                "_internal": {"value": "ignored", "confidence": "low"},
            }
        }
        parsed = _parse_llm_response(json.dumps(resp))
        assert "drug_name" in parsed
        assert "_internal" not in parsed


# ── _assess_confidence tests ────────────────────────────────────────────

class TestAssessConfidence:
    def test_high_confidence_no_review(self):
        parsed = {
            "patient_name": {"value": "Sarah Martinez", "confidence": "high"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
        }
        result = _assess_confidence(parsed)
        assert not result.needs_review
        assert result.review_reasons == []
        assert result.fields["drug_name"] == "Ozempic"

    def test_medium_confidence_no_review(self):
        parsed = {
            "patient_name": {"value": "Sarah Martinez", "confidence": "medium"},
            "member_id": {"value": "UHC8842910", "confidence": "medium"},
            "drug_name": {"value": "Ozempic", "confidence": "medium"},
        }
        result = _assess_confidence(parsed)
        assert not result.needs_review

    def test_low_confidence_critical_triggers_review(self):
        parsed = {
            "patient_name": {"value": "J. Smith", "confidence": "low"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
        }
        result = _assess_confidence(parsed)
        assert result.needs_review
        assert any("patient_name" in r for r in result.review_reasons)

    def test_missing_critical_field_triggers_review(self):
        parsed = {
            "patient_name": {"value": None, "confidence": "low"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
        }
        result = _assess_confidence(parsed)
        assert result.needs_review
        assert any("missing" in r.lower() for r in result.review_reasons)

    def test_empty_string_critical_triggers_review(self):
        parsed = {
            "patient_name": {"value": "  ", "confidence": "high"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
        }
        result = _assess_confidence(parsed)
        assert result.needs_review

    def test_low_confidence_non_critical_no_review(self):
        """Low confidence on non-critical fields should NOT trigger review."""
        parsed = {
            "patient_name": {"value": "Sarah Martinez", "confidence": "high"},
            "member_id": {"value": "UHC8842910", "confidence": "high"},
            "drug_name": {"value": "Ozempic", "confidence": "high"},
            "dose": {"value": "maybe 10mg?", "confidence": "low"},
            "prescriber_npi": {"value": "0000000000", "confidence": "low"},
        }
        result = _assess_confidence(parsed)
        assert not result.needs_review

    def test_multiple_critical_failures(self):
        parsed = {
            "patient_name": {"value": None, "confidence": "low"},
            "member_id": {"value": None, "confidence": "low"},
            "drug_name": {"value": "maybe aspirin?", "confidence": "low"},
        }
        result = _assess_confidence(parsed)
        assert result.needs_review
        assert len(result.review_reasons) == 3


# ── ExtractionResult.to_dict tests ──────────────────────────────────────

class TestExtractionResultToDict:
    def test_to_dict_flattens_fields(self):
        result = ExtractionResult(
            fields={"drug_name": "Ozempic", "dose": "10mg"},
            confidence={"drug_name": "high", "dose": "medium"},
            raw_text="some text",
        )
        d = result.to_dict()
        assert d["drug_name"] == "Ozempic"
        assert d["dose"] == "10mg"
        assert d["raw_text"] == "some text"
        assert d["_confidence"]["drug_name"] == "high"
        assert "_needs_review" not in d

    def test_to_dict_includes_review_flags(self):
        result = ExtractionResult(
            fields={"drug_name": "Ozempic"},
            confidence={"drug_name": "high"},
            needs_review=True,
            review_reasons=["member_id missing"],
        )
        d = result.to_dict()
        assert d["_needs_review"] is True
        assert d["_review_reasons"] == ["member_id missing"]

    def test_to_dict_omits_none_values(self):
        result = ExtractionResult(
            fields={"drug_name": "Ozempic", "dose": None, "icd10": None},
            confidence={"drug_name": "high"},
        )
        d = result.to_dict()
        assert "drug_name" in d
        assert "dose" not in d
        assert "icd10" not in d


# ── extract_with_llm tests (mocked HTTP) ───────────────────────────────

class TestExtractWithLlm:
    def test_successful_extraction(self):
        mock_resp = _make_httpx_response(_good_llm_response())

        with patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(extract_with_llm("Patient: Sarah Martinez\nDrug: Ozempic"))

        assert result.fields["patient_name"] == "Sarah Martinez"
        assert result.fields["drug_name"] == "Ozempic"
        assert result.confidence["drug_name"] == "high"
        assert not result.needs_review

    def test_missing_api_key_raises(self):
        with patch("src.tools.llm_extract.get_settings",
                    return_value=_mock_settings(openrouter_api_key="")):
            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
                asyncio.run(extract_with_llm("some text"))

    def test_low_confidence_triggers_review(self):
        mock_resp = _make_httpx_response(_low_confidence_response())

        with patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(extract_with_llm("Drug: Ozempic"))

        assert result.needs_review
        assert len(result.review_reasons) > 0

    def test_http_error_retries_and_raises(self):
        import httpx as httpx_mod
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx_mod.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_resp
        )

        with patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="HTTP 500"):
                asyncio.run(extract_with_llm("some text"))

        # Should have attempted twice
        assert mock_client.post.call_count == 2

    def test_malformed_json_retries(self):
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {
            "choices": [{"message": {"content": "not json at all"}}]
        }
        bad_resp.raise_for_status = MagicMock()

        good_resp = _make_httpx_response(_good_llm_response())

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_resp
            return good_resp

        with patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(extract_with_llm("some text"))

        # Second attempt should succeed
        assert result.fields["drug_name"] == "Ozempic"
        assert call_count == 2


# ── _extract_pdf_text tests ─────────────────────────────────────────────

class TestExtractPdfText:
    def test_extracts_text_from_valid_pdf(self):
        # Create a minimal PDF with pdfplumber-readable content
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            pytest.skip("pdfplumber not installed")

        # Use a real minimal PDF for testing
        from io import BytesIO
        # Minimal PDF that pdfplumber can open (even if text is empty)
        # This is a valid PDF 1.0 with no text content
        minimal_pdf = (
            b"%PDF-1.0\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"startxref\n198\n%%EOF"
        )
        # This PDF has no text, so extraction should return empty string
        text = asyncio.run(_extract_pdf_text(minimal_pdf))
        # Empty is fine — the caller handles the empty case
        assert isinstance(text, str)


# ── parse_prescription end-to-end tests (mocked) ───────────────────────

class TestParsePrescrptionE2E:
    def test_successful_parse(self):
        mock_resp = _make_httpx_response(_good_llm_response())

        fake_pdf_text = "Patient: Sarah Martinez\nDrug: Ozempic\nNDC: 00169-4130-12"

        with patch("src.tools.execute._extract_pdf_text", new_callable=AsyncMock) as mock_pdf, \
             patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_pdf.return_value = fake_pdf_text

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(parse_prescription(b"%PDF-fake"))

        assert result["drug_name"] == "Ozempic"
        assert result["patient_name"] == "Sarah Martinez"
        assert result["member_id"] == "UHC8842910"
        assert result["raw_text"] == fake_pdf_text[:2000]
        assert "_confidence" in result
        assert "_needs_review" not in result  # All high confidence

    def test_empty_pdf_raises(self):
        with patch("src.tools.execute._extract_pdf_text", new_callable=AsyncMock) as mock_pdf:
            mock_pdf.return_value = ""

            with pytest.raises(RuntimeError, match="empty content"):
                asyncio.run(parse_prescription(b"%PDF-fake"))

    def test_whitespace_only_pdf_raises(self):
        with patch("src.tools.execute._extract_pdf_text", new_callable=AsyncMock) as mock_pdf:
            mock_pdf.return_value = "   \n\t\n   "

            with pytest.raises(RuntimeError, match="empty content"):
                asyncio.run(parse_prescription(b"%PDF-fake"))

    def test_needs_review_propagated(self):
        mock_resp = _make_httpx_response(_low_confidence_response())

        with patch("src.tools.execute._extract_pdf_text", new_callable=AsyncMock) as mock_pdf, \
             patch("src.tools.llm_extract.get_settings", return_value=_mock_settings()), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_pdf.return_value = "Drug: Ozempic\nPatient: unclear"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(parse_prescription(b"%PDF-fake"))

        assert result.get("_needs_review") is True
        assert len(result.get("_review_reasons", [])) > 0


# ── No fixture fallback tests ──────────────────────────────────────────

class TestNoFixtureFallback:
    """Verify that the new code NEVER returns hardcoded fixture data."""

    def test_no_stub_for_size_function(self):
        """The _stub_for_size function should not exist in execute.py."""
        import src.tools.execute as mod
        assert not hasattr(mod, "_stub_for_size"), (
            "_stub_for_size still exists — fixture fallback was not removed"
        )

    def test_no_local_parse_function(self):
        """The _local_parse function should not exist in execute.py."""
        import src.tools.execute as mod
        assert not hasattr(mod, "_local_parse"), (
            "_local_parse still exists — fixture fallback was not removed"
        )

    def test_no_fixture_mode_in_parse(self):
        """parse_prescription should not check demo_fixture_mode."""
        import ast
        import inspect
        import textwrap
        import src.tools.execute as mod
        source = inspect.getsource(mod.parse_prescription)
        # Parse the AST and strip the docstring — we only care about the
        # executable body, not comments about what was removed.
        tree = ast.parse(textwrap.dedent(source))
        func = tree.body[0]
        # Remove docstring (first Expr node if it's a Constant string)
        if (func.body and isinstance(func.body[0], ast.Expr)
                and isinstance(func.body[0].value, ast.Constant)
                and isinstance(func.body[0].value.value, str)):
            func.body.pop(0)
        body_source = ast.unparse(tree)
        assert "demo_fixture_mode" not in body_source, (
            "parse_prescription still references demo_fixture_mode"
        )
        assert "_stub_for_size" not in body_source, (
            "parse_prescription still calls _stub_for_size"
        )
        assert "_local_parse" not in body_source, (
            "parse_prescription still calls _local_parse"
        )

    def test_no_sarah_martinez(self):
        """No hardcoded patient names in execute.py."""
        import inspect
        import src.tools.execute as mod
        source = inspect.getsource(mod)
        assert "Sarah Martinez" not in source
        assert "Lisinopril" not in source
        assert "Metformin" not in source


# ── Critical fields constant tests ──────────────────────────────────────

class TestCriticalFields:
    def test_critical_fields_include_essentials(self):
        assert "patient_name" in CRITICAL_FIELDS
        assert "member_id" in CRITICAL_FIELDS
        assert "drug_name" in CRITICAL_FIELDS

    def test_non_critical_excluded(self):
        assert "dose" not in CRITICAL_FIELDS
        assert "prescriber_npi" not in CRITICAL_FIELDS
