"""Mock payer adapter — deterministic fixture-based responses.

Used when MOCK_PAYER=true or DEMO_FIXTURE_MODE=true. Reproduces the same
behavior the old self-hosted portal provided, but through the PayerAdapter
interface so the agent code is payer-agnostic.
"""

from __future__ import annotations

import uuid

from .base import (
    AppealResult,
    PARequest,
    PayerAdapter,
    PayerStatus,
    RequirementsResult,
    StatusResult,
    SubmitResult,
)


# Deterministic approval rules matching the demo fixtures.
_AUTO_APPROVE_DRUGS = {"lisinopril", "metformin"}
_AUTO_DENY_DRUGS: set[str] = set()  # none in the current demo set


class MockPayerAdapter(PayerAdapter):
    """In-memory mock that returns deterministic results for demo/dev."""

    def __init__(self) -> None:
        # Track submitted PAs so check_status can return them.
        self._store: dict[str, dict] = {}

    async def submit_pa(self, request: PARequest) -> SubmitResult:
        ext_ref = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        drug_lower = (request.drug_name or "").lower()

        if drug_lower in _AUTO_APPROVE_DRUGS:
            status = PayerStatus.APPROVED
        elif drug_lower in _AUTO_DENY_DRUGS:
            status = PayerStatus.DENIED
        else:
            status = PayerStatus.PENDING

        self._store[ext_ref] = {
            "status": status,
            "drug": request.drug_name,
            "member_id": request.member_id,
            "denial_reason": None,
        }

        return SubmitResult(
            external_reference_id=ext_ref,
            status=status,
            receipt_url=f"/receipt/mock/{ext_ref}",
            raw_response={"mock": True},
        )

    async def check_status(self, external_reference_id: str) -> StatusResult:
        record = self._store.get(external_reference_id)
        if record is None:
            # Treat unknown refs as pending (mirrors CoverMyMeds behavior
            # for very-recently-submitted PAs that haven't propagated yet).
            return StatusResult(
                external_reference_id=external_reference_id,
                status=PayerStatus.PENDING,
            )

        return StatusResult(
            external_reference_id=external_reference_id,
            status=record["status"],
            denial_reason=record.get("denial_reason"),
        )

    async def get_requirements(
        self, drug_ndc: str, plan_id: str
    ) -> RequirementsResult:
        # Simple fixture logic: specialty drugs require PA, generics don't.
        requires = not drug_ndc.startswith("0000")  # generic prefix convention
        return RequirementsResult(
            requires_pa=requires,
            criteria=[
                "Patient has tried and failed first-line therapy",
                "Clinical documentation of medical necessity",
            ]
            if requires
            else [],
            form_url=f"/portal/healthfirst/prior-auth?ndc={drug_ndc}",
        )

    async def submit_appeal(
        self, external_reference_id: str, appeal_reason: str
    ) -> AppealResult:
        appeal_ref = f"MOCK-APL-{uuid.uuid4().hex[:8].upper()}"
        record = self._store.get(external_reference_id, {})

        # Mock appeals always move to pending review.
        record["status"] = PayerStatus.PENDING
        self._store[external_reference_id] = record

        return AppealResult(
            external_reference_id=external_reference_id,
            appeal_reference_id=appeal_ref,
            status=PayerStatus.PENDING,
            raw_response={"mock": True, "appeal_reason": appeal_reason},
        )
