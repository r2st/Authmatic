"""CoverMyMeds ePA adapter — real payer integration.

CoverMyMeds (a McKesson company) is the largest ePA network in the US,
connecting to 75%+ of commercial payers. This adapter wraps their REST
API for:
  - PA creation (submit_pa)
  - Status polling (check_status)
  - Formulary / requirements lookup (get_requirements)
  - Appeal submission (submit_appeal)

API docs: https://developers.covermymeds.com/

Auth: HTTP Basic with API key as username, "x" as password (their convention).
All responses are JSON with a `data` wrapper.

Retry policy: exponential backoff for 429 / 5xx, immediate fail for 4xx.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from .base import (
    AppealResult,
    PARequest,
    PayerAdapter,
    PayerError,
    PayerStatus,
    RequirementsResult,
    StatusResult,
    SubmitResult,
)

_logger = logging.getLogger("authmatic.payer.covermymeds")

_DEFAULT_BASE = "https://api.covermymeds.com"
_TIMEOUT = 30
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5  # seconds; actual = base ** attempt

# CoverMyMeds status strings → our canonical enum.
_STATUS_MAP: dict[str, PayerStatus] = {
    "New": PayerStatus.SUBMITTED,
    "Sent to Plan": PayerStatus.PENDING,
    "Pending": PayerStatus.PENDING,
    "Approved": PayerStatus.APPROVED,
    "Denied": PayerStatus.DENIED,
    "Appealed": PayerStatus.PENDING,
    "Cancelled": PayerStatus.CANCELLED,
    "Closed - Approved": PayerStatus.APPROVED,
    "Closed - Denied": PayerStatus.DENIED,
    "Need More Info": PayerStatus.NEEDS_INFO,
}


def _map_status(cmm_status: str) -> PayerStatus:
    return _STATUS_MAP.get(cmm_status, PayerStatus.PENDING)


class CoverMyMedsAdapter(PayerAdapter):
    """Production adapter for the CoverMyMeds ePA network."""

    def __init__(
        self,
        api_key: str,
        api_base: str = _DEFAULT_BASE,
    ):
        if not api_key:
            raise PayerError("COVERMYMEDS_API_KEY is required for the CoverMyMeds adapter")
        self._api_key = api_key
        self._base = api_base.rstrip("/")
        self._auth = (api_key, "x")  # CMM convention: key as user, "x" as pass

    # ── HTTP helpers ─────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request with retry + backoff."""
        import asyncio

        url = f"{self._base}{path}"
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.request(
                        method,
                        url,
                        json=json,
                        params=params,
                        auth=self._auth,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                    )

                if resp.status_code == 429 or resp.status_code >= 500:
                    wait = _BACKOFF_BASE**attempt
                    _logger.warning(
                        "covermymeds.retry",
                        extra={
                            "attempt": attempt,
                            "status": resp.status_code,
                            "wait_s": wait,
                            "path": path,
                        },
                    )
                    await asyncio.sleep(wait)
                    last_exc = PayerError(
                        f"CoverMyMeds {resp.status_code}: {resp.text[:200]}",
                        retryable=True,
                        status_code=resp.status_code,
                    )
                    continue

                if resp.status_code >= 400:
                    raise PayerError(
                        f"CoverMyMeds {resp.status_code}: {resp.text[:200]}",
                        retryable=False,
                        status_code=resp.status_code,
                    )

                return resp.json()

            except httpx.HTTPError as e:
                wait = _BACKOFF_BASE**attempt
                _logger.warning(
                    "covermymeds.network_error",
                    extra={"attempt": attempt, "error": str(e), "path": path},
                )
                last_exc = PayerError(str(e), retryable=True)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)

        raise last_exc or PayerError("CoverMyMeds request failed after retries")

    # ── PayerAdapter implementation ──────────────────────────────────────

    async def submit_pa(self, request: PARequest) -> SubmitResult:
        """Create a PA request via the CoverMyMeds API.

        POST /requests
        Payload follows the CoverMyMeds request creation schema.
        """
        payload = {
            "request": {
                "urgent": False,
                "prescription": {
                    "drug_id": request.drug_ndc or "",
                    "quantity": request.dose or "",
                    "frequency": "as directed",
                    "refills": 0,
                },
                "patient": {
                    "first_name": _first_name(request.patient_name),
                    "last_name": _last_name(request.patient_name),
                    "date_of_birth": request.patient_dob,
                    "member_id": request.member_id,
                },
                "prescriber": {
                    "npi": request.provider_npi or "",
                    "first_name": _first_name(request.provider_name or ""),
                    "last_name": _last_name(request.provider_name or ""),
                },
                "memo": request.rationale or "",
            }
        }

        data = await self._request("POST", "/requests", json=payload)

        pa_data = data.get("data", data.get("request", data))
        ext_id = str(pa_data.get("id", ""))
        cmm_status = pa_data.get("workflow_status", "New")

        _logger.info(
            "covermymeds.submitted",
            extra={"external_ref": ext_id, "status": cmm_status},
        )

        return SubmitResult(
            external_reference_id=ext_id,
            status=_map_status(cmm_status),
            receipt_url=pa_data.get("tokens", {}).get("html_url"),
            raw_response=pa_data,
        )

    async def check_status(self, external_reference_id: str) -> StatusResult:
        """GET /requests/{id} — poll current PA status."""
        data = await self._request("GET", f"/requests/{external_reference_id}")

        pa_data = data.get("data", data.get("request", data))
        cmm_status = pa_data.get("workflow_status", "Pending")
        denial_reason = None

        if _map_status(cmm_status) == PayerStatus.DENIED:
            events = pa_data.get("events", [])
            for event in reversed(events):
                if "deny" in event.get("type", "").lower():
                    denial_reason = event.get("description", "")
                    break
            if not denial_reason:
                denial_reason = pa_data.get("plan_outcome", {}).get(
                    "denial_reason", "Denied by payer"
                )

        return StatusResult(
            external_reference_id=external_reference_id,
            status=_map_status(cmm_status),
            denial_reason=denial_reason,
            last_updated=pa_data.get("updated_at")
            or datetime.now(timezone.utc).isoformat(),
            raw_response=pa_data,
        )

    async def get_requirements(
        self, drug_ndc: str, plan_id: str
    ) -> RequirementsResult:
        """GET /drug_search — check formulary status and PA requirements.

        CoverMyMeds provides a drug search endpoint that returns whether a
        drug requires PA under a given plan.
        """
        params = {"ndc": drug_ndc, "plan_id": plan_id}
        data = await self._request("GET", "/drug_search", params=params)

        drug_data = data.get("data", data)
        pa_required = drug_data.get("pa_required", True)
        criteria_list: list[str] = []

        forms = drug_data.get("forms", [])
        for form in forms:
            questions = form.get("questions", [])
            for q in questions:
                if q.get("question"):
                    criteria_list.append(q["question"])

        return RequirementsResult(
            requires_pa=pa_required,
            criteria=criteria_list or ["Prior authorization required per plan formulary"],
            form_url=drug_data.get("form_url"),
            raw_response=drug_data,
        )

    async def submit_appeal(
        self, external_reference_id: str, appeal_reason: str
    ) -> AppealResult:
        """POST /requests/{id}/appeals — submit an appeal for a denied PA."""
        payload = {
            "appeal": {
                "appeal_reason": appeal_reason,
            }
        }

        data = await self._request(
            "POST",
            f"/requests/{external_reference_id}/appeals",
            json=payload,
        )

        appeal_data = data.get("data", data.get("appeal", data))
        appeal_id = str(appeal_data.get("id", ""))
        cmm_status = appeal_data.get("workflow_status", "Appealed")

        _logger.info(
            "covermymeds.appeal_submitted",
            extra={
                "external_ref": external_reference_id,
                "appeal_ref": appeal_id,
            },
        )

        return AppealResult(
            external_reference_id=external_reference_id,
            appeal_reference_id=appeal_id,
            status=_map_status(cmm_status),
            raw_response=appeal_data,
        )


# ── Helpers ──────────────────────────────────────────────────────────────


def _first_name(full: str) -> str:
    parts = full.strip().replace(",", "").split()
    return parts[0] if parts else ""


def _last_name(full: str) -> str:
    parts = full.strip().replace(",", "").split()
    return " ".join(parts[1:]).rstrip(",").strip() if len(parts) > 1 else ""
