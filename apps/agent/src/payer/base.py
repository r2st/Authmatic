"""PayerAdapter — abstract interface for payer integrations.

Every adapter (mock, CoverMyMeds, future direct-payer) implements this
protocol so the agent loop and persist layer stay payer-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class PayerStatus(str, Enum):
    """Canonical status values across all payer integrations."""

    SUBMITTED = "submitted"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    NEEDS_INFO = "needs_info"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class SubmitResult:
    """Returned by submit_pa on success."""

    external_reference_id: str
    status: PayerStatus
    receipt_url: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StatusResult:
    """Returned by check_status."""

    external_reference_id: str
    status: PayerStatus
    denial_reason: str | None = None
    last_updated: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RequirementsResult:
    """Returned by get_requirements — what the payer needs for this drug/plan."""

    requires_pa: bool
    criteria: list[str] = field(default_factory=list)
    form_url: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AppealResult:
    """Returned by submit_appeal."""

    external_reference_id: str
    appeal_reference_id: str
    status: PayerStatus
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PARequest:
    """The canonical prior-auth request payload passed to every adapter."""

    patient_name: str
    patient_dob: str
    member_id: str
    drug_name: str
    drug_ndc: str | None = None
    dose: str | None = None
    diagnosis_code: str | None = None
    provider_name: str | None = None
    provider_npi: str | None = None
    rationale: str | None = None
    plan_id: str | None = None


class PayerAdapter(ABC):
    """Protocol every payer integration must implement.

    Methods are async so adapters can make HTTP calls, hit queues, etc.
    """

    @abstractmethod
    async def submit_pa(self, request: PARequest) -> SubmitResult:
        """Submit a prior-authorization request to the payer.

        Returns a SubmitResult with the payer's external reference ID and
        initial status. Raises PayerError on unrecoverable failure.
        """

    @abstractmethod
    async def check_status(self, external_reference_id: str) -> StatusResult:
        """Poll the payer for the current status of a submitted PA.

        Returns the latest status. Raises PayerError if the reference is
        unknown or the payer is unreachable.
        """

    @abstractmethod
    async def get_requirements(
        self, drug_ndc: str, plan_id: str
    ) -> RequirementsResult:
        """Query whether a drug requires PA under a given plan, and what
        clinical criteria must be met.
        """

    @abstractmethod
    async def submit_appeal(
        self, external_reference_id: str, appeal_reason: str
    ) -> AppealResult:
        """Submit an appeal for a denied PA."""


class PayerError(Exception):
    """Raised when a payer integration fails in a way the caller should handle."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
