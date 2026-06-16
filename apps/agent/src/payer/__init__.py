"""Payer adapter layer — pluggable integration for PA submission.

Select an adapter at startup based on configuration:
  - MOCK_PAYER=true  → MockPayerAdapter  (deterministic fixture replay)
  - Otherwise        → CoverMyMedsAdapter (real ePA network)
"""

from __future__ import annotations

from ..settings import get_settings
from .base import PayerAdapter
from .covermymeds import CoverMyMedsAdapter
from .mock import MockPayerAdapter


def get_payer_adapter() -> PayerAdapter:
    """Return the adapter matching the current configuration.

    Reads MOCK_PAYER from the environment (via Settings). When true *or*
    when demo_fixture_mode is on, the mock adapter is used so demo/dev
    never hits a real payer network.
    """
    s = get_settings()
    if s.mock_payer or s.demo_fixture_mode:
        return MockPayerAdapter()
    return CoverMyMedsAdapter(
        api_key=s.covermymeds_api_key,
        api_base=s.covermymeds_api_base,
    )


__all__ = [
    "PayerAdapter",
    "MockPayerAdapter",
    "CoverMyMedsAdapter",
    "get_payer_adapter",
]
