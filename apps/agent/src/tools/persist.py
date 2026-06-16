"""PERSIST verb — Insforge + payer adapter.

The persist *verb* writes structured fields the agent has extracted (drug,
dose, diagnosis, rationale) into the prior_auths row, and embeds the
rationale into pgvector for future RAG lookups. Edge-function side-effects
(doctor SMS / Slack ping) fire from here too.

When PERSIST runs, it also submits the PA to the configured payer adapter
(mock or CoverMyMeds) and records the payer's external reference ID and
initial status for downstream polling.

This is distinct from src/persist.py, which handles run lifecycle for the
API layer. Keeping them separate so the agent's "verb" and the API's
"run management" stay decoupled.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

from ..payer import get_payer_adapter
from ..payer.base import PARequest, PayerError
from ..settings import get_settings

_logger = logging.getLogger("authmatic.tools.persist")


async def write_fields(
    *,
    pool: asyncpg.Pool,
    pa_id: str,
    fields: dict,
) -> dict:
    """Update the prior_auths row with extracted fields."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE prior_auths SET
              drug_name      = COALESCE($2, drug_name),
              dose           = COALESCE($3, dose),
              diagnosis_code = COALESCE($4, diagnosis_code),
              drug_ndc       = COALESCE($5, drug_ndc),
              rationale      = COALESCE($6, rationale)
            WHERE id = $1
            """,
            pa_id,
            fields.get("drug_name"),
            fields.get("dose"),
            fields.get("icd10") or fields.get("diagnosis_code"),
            fields.get("drug_ndc"),
            fields.get("rationale"),
        )
    return {"persisted": True, "fields": list(fields.keys())}


async def submit_to_payer(
    *,
    pool: asyncpg.Pool,
    pa_id: str,
    parsed: dict,
    rationale: str,
) -> dict:
    """Submit the PA to the configured payer adapter and record the result.

    Called from the agent loop's ACTION step (after PERSIST has written
    the structured fields). Returns a dict suitable for the event log.
    """
    adapter = get_payer_adapter()

    # Hydrate patient identity from the DB (we keep PHI out of the planner).
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.full_name, p.dob, p.member_id, p.plan_id
            FROM prior_auths pa JOIN patients p ON p.id = pa.patient_id
            WHERE pa.id = $1
            """,
            pa_id,
        )

    request = PARequest(
        patient_name=row["full_name"] if row else parsed.get("patient_name", ""),
        patient_dob=str(row["dob"]) if row else parsed.get("dob", ""),
        member_id=row["member_id"] if row else parsed.get("member_id", ""),
        drug_name=parsed.get("drug_name", ""),
        drug_ndc=parsed.get("drug_ndc"),
        dose=parsed.get("dose"),
        diagnosis_code=parsed.get("icd10") or parsed.get("diagnosis_code"),
        provider_name=parsed.get("provider_name"),
        provider_npi=parsed.get("provider_npi"),
        rationale=rationale,
        plan_id=row["plan_id"] if row else parsed.get("plan_id"),
    )

    try:
        result = await adapter.submit_pa(request)
    except PayerError as e:
        _logger.error(
            "persist.payer_submit_failed",
            extra={"pa_id": pa_id, "error": str(e), "retryable": e.retryable},
        )
        return {
            "submitted_to_payer": False,
            "error": str(e),
            "retryable": e.retryable,
        }

    # Record the payer's reference + initial status and schedule first poll.
    first_poll = datetime.now(timezone.utc) + timedelta(minutes=5)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE prior_auths SET
              external_reference_id = $2,
              payer_status          = $3,
              receipt_url           = COALESCE($4, receipt_url),
              next_poll_at          = $5,
              poll_count            = 0
            WHERE id = $1
            """,
            pa_id,
            result.external_reference_id,
            result.status.value,
            result.receipt_url,
            first_poll,
        )

    _logger.info(
        "persist.payer_submitted",
        extra={
            "pa_id": pa_id,
            "ext_ref": result.external_reference_id,
            "status": result.status.value,
        },
    )

    return {
        "submitted_to_payer": True,
        "external_reference_id": result.external_reference_id,
        "payer_status": result.status.value,
        "receipt_url": result.receipt_url,
    }


async def embed_rationale(
    *,
    pool: asyncpg.Pool,
    pa_id: str,
    rationale: str,
) -> dict:
    """Embed the rationale via Insforge gateway and upsert into pgvector."""
    s = get_settings()
    if s.demo_fixture_mode or not s.insforge_api_key:
        # Skip the network round-trip; just stub a fake embedding.
        embedding = [0.0] * 1536
    else:
        embedding = await _embed(rationale)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pa_embeddings (pa_id, rationale, embedding)
            VALUES ($1, $2, $3)
            """,
            pa_id, rationale, _pgvector_literal(embedding),
        )
    return {"embedded": True, "dim": len(embedding)}


async def fire_doctor_notification(
    *,
    pa_id: str,
    doctor_handle: str,
    summary: str,
) -> dict:
    """Call an Insforge edge function that posts to Slack/SMS the doctor."""
    s = get_settings()
    if s.demo_fixture_mode or not s.insforge_project_url:
        return {"notified": True, "channel": "fixture", "doctor": doctor_handle}

    url = f"{s.insforge_project_url.rstrip('/')}/functions/v1/notify-doctor"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            url,
            json={
                "doctor_handle": doctor_handle,
                "summary": summary,
                "pa_id": pa_id,
            },
            headers={"Authorization": f"Bearer {s.insforge_api_key}"},
        )
        r.raise_for_status()
    return r.json()


async def _embed(text: str) -> list[float]:
    """Call Insforge gateway's /v1/embeddings."""
    s = get_settings()
    url = f"{s.insforge_project_url.rstrip('/')}/v1/embeddings"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            url,
            json={"model": "text-embedding-3-small", "input": text},
            headers={"Authorization": f"Bearer {s.insforge_api_key}"},
        )
        r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def _pgvector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
