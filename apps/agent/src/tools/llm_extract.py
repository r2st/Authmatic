"""LLM-based structured extraction from prescription PDF text.

Replaces the regex+fixture fallback with a real OpenRouter LLM call that
extracts patient, drug, and clinical fields from raw PDF text. Each field
gets a confidence score. Critical fields at low confidence trigger a
needs_review status rather than proceeding with bad data.

Never falls back to hardcoded fixture data. If extraction fails, it fails
explicitly with a clear error.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..settings import get_settings

_logger = logging.getLogger("authmatic.agent.extract")

# ── Extraction schema ───────────────────────────────────────────────────
# The LLM is asked to return these fields. Each field is tagged with a
# confidence level (high / medium / low) based on how clearly the source
# text supports the extracted value.

EXTRACTION_FIELDS: list[dict[str, str]] = [
    {"name": "patient_name", "description": "Full name of the patient", "required": "true"},
    {"name": "dob", "description": "Patient date of birth (YYYY-MM-DD)", "required": "false"},
    {"name": "member_id", "description": "Insurance member/subscriber ID", "required": "true"},
    {"name": "insurance_id", "description": "Insurance plan or group ID", "required": "false"},
    {"name": "drug_name", "description": "Requested medication name", "required": "true"},
    {"name": "drug_ndc", "description": "National Drug Code (NDC) in format XXXXX-XXXX-XX or similar", "required": "false"},
    {"name": "dose", "description": "Dosage and frequency (e.g. '10mg daily', '40mg every 2 weeks')", "required": "false"},
    {"name": "icd10", "description": "Primary ICD-10 diagnosis code (e.g. E11.9, I10)", "required": "false"},
    {"name": "icd_codes", "description": "All ICD-10 codes mentioned, as a JSON array of strings", "required": "false"},
    {"name": "prescriber_name", "description": "Name of the prescribing physician/provider", "required": "false"},
    {"name": "prescriber_npi", "description": "Prescriber NPI number (10-digit)", "required": "false"},
    {"name": "diagnosis", "description": "Diagnosis description in plain text", "required": "false"},
    {"name": "patient_ssn", "description": "Patient SSN if present (XXX-XX-XXXX)", "required": "false"},
]

# Fields that MUST have high or medium confidence for a run to proceed.
# Low confidence on any of these triggers needs_review.
CRITICAL_FIELDS = frozenset({"patient_name", "member_id", "drug_name"})


def _build_extraction_prompt(pdf_text: str) -> str:
    """Build the system + user prompt for structured extraction."""
    field_descriptions = "\n".join(
        f"  - {f['name']}: {f['description']} (required: {f['required']})"
        for f in EXTRACTION_FIELDS
    )

    system = (
        "You are a medical document extraction system. You extract structured "
        "fields from prescription and prior authorization documents. You MUST "
        "return valid JSON and nothing else.\n\n"
        "For each field you extract, also provide a confidence level:\n"
        "  - \"high\": the value is clearly and unambiguously stated in the text\n"
        "  - \"medium\": the value is likely correct but the text is somewhat ambiguous\n"
        "  - \"low\": the value is a guess or the text is unclear/contradictory\n\n"
        "If a field is not found in the text at all, set its value to null and "
        "confidence to \"low\".\n\n"
        "Return a JSON object with this exact structure:\n"
        "{\n"
        '  "fields": {\n'
        '    "<field_name>": {"value": "<extracted value or null>", "confidence": "high|medium|low"},\n'
        "    ...\n"
        "  }\n"
        "}\n\n"
        f"Fields to extract:\n{field_descriptions}"
    )

    user = (
        "Extract all fields from the following prescription/prior-authorization "
        "document text. Return ONLY the JSON object, no other text.\n\n"
        f"--- DOCUMENT TEXT ---\n{pdf_text[:8000]}\n--- END ---"
    )

    return system, user


@dataclass
class ExtractionResult:
    """Parsed extraction with per-field confidence."""

    fields: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, str] = field(default_factory=dict)
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Flatten to the dict format the rest of the pipeline expects."""
        out: dict[str, Any] = {}
        for k, v in self.fields.items():
            if v is not None:
                out[k] = v
        out["_confidence"] = dict(self.confidence)
        if self.needs_review:
            out["_needs_review"] = True
            out["_review_reasons"] = self.review_reasons
        if self.raw_text:
            out["raw_text"] = self.raw_text
        return out


def _parse_llm_response(raw_json: str) -> dict[str, dict[str, Any]]:
    """Parse the LLM's JSON response into {field: {value, confidence}}.

    Handles minor variations in response format. Raises ValueError on
    unparseable output.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_json, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Normalize: the LLM should return {"fields": {...}} but might return
    # the fields dict directly.
    if "fields" in data and isinstance(data["fields"], dict):
        fields = data["fields"]
    else:
        # Assume the top-level dict IS the fields dict
        fields = data

    result: dict[str, dict[str, Any]] = {}
    for key, val in fields.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and "value" in val:
            result[key] = {
                "value": val.get("value"),
                "confidence": val.get("confidence", "medium"),
            }
        else:
            # LLM returned a plain value without confidence wrapper
            result[key] = {
                "value": val,
                "confidence": "medium",
            }

    return result


def _assess_confidence(parsed_fields: dict[str, dict[str, Any]]) -> ExtractionResult:
    """Build an ExtractionResult with confidence assessment.

    Critical fields at low confidence trigger needs_review.
    """
    result = ExtractionResult()

    for key, entry in parsed_fields.items():
        result.fields[key] = entry["value"]
        result.confidence[key] = entry["confidence"]

    # Check critical fields
    for crit in CRITICAL_FIELDS:
        value = result.fields.get(crit)
        conf = result.confidence.get(crit, "low")

        if value is None or (isinstance(value, str) and not value.strip()):
            result.needs_review = True
            result.review_reasons.append(f"Critical field '{crit}' is missing")
        elif conf == "low":
            result.needs_review = True
            result.review_reasons.append(
                f"Critical field '{crit}' has low confidence (value: {value!r})"
            )

    return result


async def extract_with_llm(pdf_text: str) -> ExtractionResult:
    """Send PDF text to OpenRouter LLM for structured extraction.

    Returns an ExtractionResult with per-field confidence. Never falls back
    to fixture data. Raises on network/API errors after logging.
    """
    s = get_settings()

    if not s.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Cannot perform LLM extraction. "
            "Set the key in .env or environment variables."
        )

    system_prompt, user_prompt = _build_extraction_prompt(pdf_text)

    url = f"{s.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": s.insforge_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {s.openrouter_api_key}",
        "HTTP-Referer": s.insforge_project_url or "https://authmatic.local",
        "X-Title": "Authmatic Extractor",
    }

    _logger.info(
        "llm_extract.request",
        extra={"model": s.insforge_model, "text_chars": len(pdf_text)},
    )

    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                raw_content = r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            _logger.error(
                "llm_extract.http_error",
                extra={"status": e.response.status_code, "attempt": attempt},
            )
            if attempt == 2:
                raise RuntimeError(
                    f"LLM extraction failed after 2 attempts: HTTP {e.response.status_code}"
                ) from e
            continue
        except (httpx.RequestError, KeyError) as e:
            _logger.error(
                "llm_extract.request_error",
                extra={"error": str(e), "attempt": attempt},
            )
            if attempt == 2:
                raise RuntimeError(
                    f"LLM extraction failed after 2 attempts: {e}"
                ) from e
            continue

        try:
            parsed_fields = _parse_llm_response(raw_content)
        except (ValueError, json.JSONDecodeError) as e:
            _logger.warning(
                "llm_extract.parse_retry",
                extra={"error": str(e), "attempt": attempt},
            )
            if attempt == 2:
                raise RuntimeError(
                    f"LLM returned unparseable response after 2 attempts: {e}"
                ) from e
            # Retry with a nudge
            payload["messages"].append({
                "role": "system",
                "content": (
                    "Your last response was not valid JSON. Return ONLY a "
                    "JSON object with the 'fields' key as described."
                ),
            })
            continue

        result = _assess_confidence(parsed_fields)
        result.raw_text = pdf_text[:2000]

        _logger.info(
            "llm_extract.success",
            extra={
                "fields_extracted": len(result.fields),
                "needs_review": result.needs_review,
                "confidences": result.confidence,
            },
        )
        return result

    # Should be unreachable — the loop above always returns or raises on attempt 2
    raise RuntimeError("LLM extraction: unreachable")  # pragma: no cover
