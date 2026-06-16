"""EXECUTE verb — LLM-based prescription PDF extraction.

Extracts structured fields from a prescription PDF using:
  1. pdfplumber to extract raw text
  2. OpenRouter LLM to parse fields with confidence scoring

If the LLM assigns low confidence to critical fields (patient_name,
member_id, drug_name), the extraction result includes a needs_review
flag so the agent loop can halt for human review.

NEVER falls back to hardcoded fixture data. If extraction fails, it fails
explicitly with a clear error.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging

from ..settings import get_settings
from .llm_extract import ExtractionResult, extract_with_llm

_logger = logging.getLogger("authmatic.agent.execute")


async def ping() -> dict:
    s = get_settings()
    if not s.openrouter_api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY not set"}
    # Verify pdfplumber is importable
    try:
        import pdfplumber  # noqa: F401
        return {"ok": True}
    except ImportError:
        return {"ok": False, "error": "pdfplumber not installed"}


async def parse_prescription(pdf_bytes: bytes) -> dict:
    """Extract structured fields from a prescription PDF.

    Returns a dict with drug_name, drug_ndc, dose, icd10, member_id,
    patient_name, and other fields. Includes _confidence scores and
    _needs_review / _review_reasons when confidence is low on critical
    fields.

    Raises RuntimeError on extraction failure — never returns fixture data.
    """
    # Step 1: Extract raw text from PDF
    pdf_text = await _extract_pdf_text(pdf_bytes)

    if not pdf_text.strip():
        raise RuntimeError(
            "PDF text extraction returned empty content. The PDF may be "
            "image-only (scanned) or corrupt. OCR support is not yet "
            "implemented."
        )

    _logger.info(
        "execute.pdf_text_extracted",
        extra={"text_length": len(pdf_text)},
    )

    # Step 2: Send to LLM for structured extraction
    result: ExtractionResult = await extract_with_llm(pdf_text)

    output = result.to_dict()

    if result.needs_review:
        _logger.warning(
            "execute.needs_review",
            extra={"reasons": result.review_reasons},
        )

    return output


async def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber. Runs in a thread
    to avoid blocking the event loop."""
    def _do_extract() -> str:
        try:
            import pdfplumber
        except ImportError as e:
            raise RuntimeError(
                "pdfplumber is required for PDF text extraction but is not "
                "installed. Add it to requirements.txt."
            ) from e

        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n".join(pages)
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract text from PDF: {e}"
            ) from e

    return await asyncio.to_thread(_do_extract)
