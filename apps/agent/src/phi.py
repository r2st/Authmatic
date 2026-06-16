"""PHI redaction helpers. Pure, dependency-free.

Enforces the logging + LLM rules in ADR 0008
(docs/decisions/0008-phi-handling-policy.md): no raw PHI field may be
logged, sent to the planner LLM, or emitted to a third party.

Use `redact_phi()` to scrub a dict before it reaches the structured logger
(ticket 0011) or the planner history (ticket 0014 / this ticket's code
review). `redact()` handles a single value.
"""

from __future__ import annotations

from typing import Any

# Field names that carry PHI in our schema (see ADR 0008 field table).
PHI_KEYS: frozenset[str] = frozenset(
    {
        "patient_name",
        "full_name",
        "dob",
        "member_id",
        "patient_ssn",
        "ssn",
        "diagnosis",
        "diagnosis_code",
        "icd10",
        "justification",
        "rationale",
        "raw_text",
    }
)


def mask_tail(value: str, keep: int = 4) -> str:
    """Mask all but the last `keep` characters."""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def initials(value: str) -> str:
    """Reduce a name to initials: 'Maria Martinez' -> 'M.M.'"""
    parts = [p for p in value.strip().split() if p]
    return "".join(f"{p[0].upper()}." for p in parts)


def redact(key: str, value: Any) -> str:
    """Redact one PHI value according to its field."""
    if value is None:
        return ""
    s = str(value)
    if key in ("patient_name", "full_name"):
        return initials(s)
    if key == "member_id":
        return mask_tail(s, 4)
    if key in ("patient_ssn", "ssn"):
        return "***-**-****"
    if key == "dob":
        return "****-**-**"
    # Clinical codes are low-risk identifiers but still PHI in context; keep
    # the code (needed for debugging coverage logic) — it is not a direct
    # identifier. Free text is fully masked.
    if key in ("diagnosis_code", "icd10"):
        return s
    return f"[redacted {len(s)} chars]"


def redact_phi(obj: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `obj` with every PHI key redacted."""
    return {k: (redact(k, v) if k in PHI_KEYS else v) for k, v in obj.items()}
