"""PERSIST verb — Insforge.

The persist *verb* writes structured fields the agent has extracted (drug,
dose, diagnosis, rationale) into the prior_auths row, and embeds the
rationale into pgvector for future RAG lookups. Edge-function side-effects
(doctor SMS / Slack ping) fire from here too.

This is distinct from src/persist.py, which handles run lifecycle for the
API layer. Keeping them separate so the agent's "verb" and the API's
"run management" stay decoupled.
"""

from __future__ import annotations

import asyncpg
import httpx

from ..settings import get_settings


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
