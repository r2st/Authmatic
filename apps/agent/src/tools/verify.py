"""VERIFY verb — Opsera MCP (PHI exposure scan).

Calls Opsera's MCP `scan_pii` tool with the outgoing payer packet and an
allowlist of fields the form legitimately needs. Anything else flagged
fails the run before it touches the network.

Stores the scan result in compliance_scans so the audit page can render it.
"""

from __future__ import annotations

import json

import asyncpg
import httpx

from ..settings import get_settings

ALLOWED_FIELDS = [
    "full_name", "dob", "member_id",
    "drug_name", "drug_ndc", "dose", "diagnosis_code",
    "rationale",
]


async def ping() -> dict:
    s = get_settings()
    if s.demo_fixture_mode:
        return {"ok": True, "mode": "fixture"}
    if not s.opsera_token:
        return {"ok": False, "error": "OPSERA_TOKEN not set"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            s.opsera_mcp_url,
            headers={
                "Authorization": f"Bearer {s.opsera_token}",
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        return {"ok": r.status_code in (200, 202), "status": r.status_code}


async def scan_phi_exposure(
    *,
    pool: asyncpg.Pool,
    pa_id: str,
    packet: dict,
) -> dict:
    s = get_settings()

    if s.demo_fixture_mode:
        result = _fixture_scan(packet)
    else:
        result = await _call_opsera_scan(packet)

    await _record_scan(pool, pa_id, result)
    return result


async def _call_opsera_scan(packet: dict) -> dict:
    """Invoke the Opsera MCP scan_pii tool via streamable-HTTP transport."""
    s = get_settings()

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "scan_pii",
            "arguments": {
                "content": json.dumps(packet),
                "context": "healthcare_prior_auth",
                "allowed_fields": ALLOWED_FIELDS,
            },
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            s.opsera_mcp_url,
            headers={
                "Authorization": f"Bearer {s.opsera_token}",
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
            json=body,
        )
        r.raise_for_status()

    # Opsera returns the structured result on `.result.structuredContent`.
    payload = r.json().get("result", {})
    structured = payload.get("structuredContent", payload)

    return {
        "passed": structured.get("risk_level", "high") in ("low", "none"),
        "flagged_fields": structured.get("flagged", []),
        "raw": structured,
    }


def _fixture_scan(packet: dict) -> dict:
    """Deterministic pass when fixture mode is on, unless the packet
    contains a field outside the allowlist."""
    extra = [k for k in packet if k not in ALLOWED_FIELDS and packet[k]]
    if extra:
        return {
            "passed": False,
            "flagged_fields": extra,
            "raw": {"risk_level": "high", "source": "fixture"},
        }
    return {
        "passed": True,
        "flagged_fields": [],
        "raw": {"risk_level": "low", "source": "fixture"},
    }


async def _record_scan(pool: asyncpg.Pool, pa_id: str, result: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO compliance_scans
              (pa_id, passed, flagged_fields, raw_response, clinic_id)
            VALUES ($1, $2, $3, $4,
                    (SELECT clinic_id FROM prior_auths WHERE id = $1))
            """,
            pa_id,
            result["passed"],
            result.get("flagged_fields", []),
            result.get("raw", {}),
        )
