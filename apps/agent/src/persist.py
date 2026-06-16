"""Run management — used by the FastAPI layer (not the agent loop itself).

The agent's PERSIST *verb* lives in src/tools/persist.py and writes per-step
side effects. This module manages whole runs: create one, fetch its detail,
replay events from durable state.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import asyncpg

from .upload import storage_key

# A demo patient gets seeded on every fresh run if none exists — see
# scripts/seed.sh for the full set. This is the fallback so a clean DB
# doesn't blow up.
# Same identity the simple Rx PDFs (Lisinopril/Metformin from gen_demo_pdfs.py)
# reference. Aligned with scripts/seed.py so a seedless boot still resolves
# the simple-PDF demo path.
_FALLBACK_PATIENT = {
    "full_name": "Jane Doe",
    "dob": date(1968, 4, 12),
    "plan_id": "UHC-CHOICE-PLUS",
    "member_id": "UHC-000000-DEMO1",
}


# Default clinic for runs without an explicit clinic (the 0006 backfill clinic).
# clinic_id is NOT NULL + FK to clinics(id) after migration 0007.
_DEFAULT_CLINIC = "00000000-0000-0000-0000-000000000001"


def coerce_clinic_id(clinic_id: str) -> str:
    """Coerce the clinic_id to a valid clinics(id) UUID. Non-UUID sentinels
    (e.g. the 'unknown' default, or a demo clinic slug) map to the backfill
    clinic so the NOT NULL + FK + UUID-column constraints (migrations 0007/
    0009) are satisfied everywhere — create_run AND queue.enqueue."""
    from uuid import UUID

    try:
        UUID(clinic_id)
        return clinic_id
    except (ValueError, TypeError):
        return _DEFAULT_CLINIC


# Backwards-compatible internal alias.
_clinic_uuid = coerce_clinic_id


async def create_run(
    pool: asyncpg.Pool, pdf_bytes: bytes, filename: str, clinic_id: str = "unknown"
) -> str:
    """Insert a fresh prior_auths row, return its UUID as str.

    For the demo, the PDF is stored to Insforge object storage and the key
    is written to trigger_pdf_key. For local dev we just keep it in-memory.
    The storage key derives uniqueness from clinic_id + run_id, never from the
    untrusted upload filename (ticket 0013).
    """
    clinic = _clinic_uuid(clinic_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Always default to the canonical Jane Doe fallback. The agent's
            # PERSIST step will swap to the real patient via member_id once
            # the PDF has been parsed.
            patient_id = await conn.fetchval(
                "SELECT id FROM patients WHERE member_id = $1",
                _FALLBACK_PATIENT["member_id"],
            )
            if patient_id is None:
                patient_id = await conn.fetchval(
                    """
                    INSERT INTO patients (full_name, dob, plan_id, member_id, clinic_id)
                    VALUES ($1, $2, $3, $4, $5) RETURNING id
                    """,
                    _FALLBACK_PATIENT["full_name"],
                    _FALLBACK_PATIENT["dob"],
                    _FALLBACK_PATIENT["plan_id"],
                    _FALLBACK_PATIENT["member_id"],
                    clinic,
                )

            run_id = await conn.fetchval(
                """
                INSERT INTO prior_auths
                  (patient_id, drug_name, status, clinic_id)
                VALUES ($1, '<pending>', 'pending', $2)
                RETURNING id
                """,
                patient_id,
                clinic,
            )

            # Safe storage key — uniqueness from clinic_id + run_id, with the
            # filename sanitized (no path traversal / collision via filename).
            # In production: upload pdf_bytes to Insforge storage under this key.
            key = storage_key(clinic_id, str(run_id), filename)
            await conn.execute(
                "UPDATE prior_auths SET trigger_pdf_key = $1 WHERE id = $2",
                key,
                run_id,
            )
    return str(run_id)


async def append_event(
    pool: asyncpg.Pool,
    pa_id: str,
    step_no: int,
    verb: str,
    plan: str,
    tool_input: dict | None,
    tool_output: dict | None,
    duration_ms: int,
) -> dict:
    """Insert one agent_events row, return it shaped for SSE."""
    async with pool.acquire() as conn:
        # clinic_id is NOT NULL (migration 0007); inherit it from the parent run.
        await conn.execute(
            """
            INSERT INTO agent_events
              (pa_id, step_no, verb, plan, tool_input, tool_output, duration_ms, clinic_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7,
                    (SELECT clinic_id FROM prior_auths WHERE id = $1))
            """,
            pa_id, step_no, verb, plan, tool_input, tool_output, duration_ms,
        )
    return {
        "step_no": step_no,
        "verb": verb,
        "plan": plan,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "duration_ms": duration_ms,
    }


async def update_status(
    pool: asyncpg.Pool,
    pa_id: str,
    status: str,
    receipt_url: str | None = None,
    drug_name: str | None = None,
    dose: str | None = None,
    diagnosis_code: str | None = None,
    drug_ndc: str | None = None,
    rationale: str | None = None,
    patient_id: str | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE prior_auths SET
              status         = $2,
              receipt_url    = COALESCE($3, receipt_url),
              drug_name      = COALESCE($4, drug_name),
              dose           = COALESCE($5, dose),
              diagnosis_code = COALESCE($6, diagnosis_code),
              drug_ndc       = COALESCE($7, drug_ndc),
              rationale      = COALESCE($8, rationale),
              patient_id     = COALESCE($9, patient_id)
            WHERE id = $1
            """,
            pa_id, status, receipt_url, drug_name, dose, diagnosis_code,
            drug_ndc, rationale, patient_id,
        )


async def link_patient_by_member_id(
    pool: asyncpg.Pool, member_id: str | None
) -> str | None:
    """Return the patient.id matching this member_id, or None if no match.

    The seed populates patients keyed by `member_id` (which is unique within a
    payer). We use that to swap the prior_auths.patient_id from the fallback
    (Jane Doe) to whoever the dropped PDF actually identifies.
    """
    if not member_id:
        return None
    async with pool.acquire() as conn:
        pid = await conn.fetchval(
            "SELECT id FROM patients WHERE member_id = $1", member_id,
        )
    return str(pid) if pid else None


async def fetch_plan_id_by_member_id(
    pool: asyncpg.Pool, member_id: str | None
) -> str | None:
    """Return the patient's plan_id (e.g. 'HF-CHOICE-PLUS') for a given
    member_id, so the agent can scope its coverage-rule lookup to the
    right payer.
    """
    if not member_id:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT plan_id FROM patients WHERE member_id = $1", member_id,
        )


async def fetch_run_detail(pool: asyncpg.Pool, run_id: str) -> dict | None:
    """Hydrate everything the audit page needs in one trip."""
    async with pool.acquire() as conn:
        pa = await conn.fetchrow("SELECT * FROM prior_auths WHERE id = $1", run_id)
        if pa is None:
            return None
        patient = await conn.fetchrow(
            "SELECT full_name, dob, plan_id, member_id FROM patients WHERE id = $1",
            pa["patient_id"],
        )
        events = await conn.fetch(
            """
            SELECT step_no, verb, plan, tool_input, tool_output, duration_ms
            FROM agent_events WHERE pa_id = $1 ORDER BY step_no
            """,
            run_id,
        )
        scan = await conn.fetchrow(
            """
            SELECT passed, flagged_fields, scanned_at
            FROM compliance_scans WHERE pa_id = $1
            ORDER BY scanned_at DESC LIMIT 1
            """,
            run_id,
        )

    return {
        "id": str(pa["id"]),
        "patient": dict(patient) if patient else None,
        "drug": {
            "name": pa["drug_name"],
            "dose": pa["dose"],
            "diagnosis_code": pa["diagnosis_code"],
        },
        "status": pa["status"],
        "receipt_url": pa["receipt_url"],
        "rationale": pa["rationale"],
        "events": [dict(r) for r in events],
        "scan": dict(scan) if scan else None,
        "created_at": pa["created_at"].isoformat(),
    }


async def fetch_run_status(pool: asyncpg.Pool, run_id: str) -> str | None:
    """The run's current status, or None if the run doesn't exist. Used by the
    SSE tailer (ticket 0028) to know when to stop streaming."""
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT status FROM prior_auths WHERE id = $1", run_id)


async def poll_events_since(
    pool: asyncpg.Pool, run_id: str, after_step: int
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT step_no, verb, plan, tool_input, tool_output, duration_ms
            FROM agent_events
            WHERE pa_id = $1 AND step_no > $2
            ORDER BY step_no
            """,
            run_id, after_step,
        )
    return [dict(r) for r in rows]


# ─── RAG over past approvals ─────────────────────────────────────────────


_DRUG_ALIASES_CACHE: dict[str, set[str]] | None = None


def _drug_aliases() -> dict[str, set[str]]:
    """brand-or-generic name (lowercased) → all known names for the same drug.

    Reads from mock_data.json so the brand/generic mapping stays in one
    canonical place. Ozempic↔semaglutide, Humira↔adalimumab, etc.
    """
    global _DRUG_ALIASES_CACHE
    if _DRUG_ALIASES_CACHE is not None:
        return _DRUG_ALIASES_CACHE

    path = (
        Path(__file__).resolve().parents[3]
        / "assets" / "fixtures" / "mock_data.json"
    )
    out: dict[str, set[str]] = {}
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        _DRUG_ALIASES_CACHE = out
        return out

    for d in data.get("drugs", []):
        names = {d.get("brand_name"), d.get("generic_name")}
        names.discard(None)
        if not names:
            continue
        lowered = {n.lower() for n in names}
        for n in lowered:
            out[n] = lowered
    _DRUG_ALIASES_CACHE = out
    return out


async def fetch_similar_approvals(
    pool: asyncpg.Pool,
    drug_name: str | None,
    icd10: str | None,
    limit: int = 3,
) -> list[dict]:
    """Return prior approved PAs whose drug (incl. brand↔generic aliases) or
    ICD-10 matches the current request. Same-drug matches outrank
    same-diagnosis-only matches.

    SQL-keyed retrieval today; the schema and `pa_embeddings` table are in
    place for swapping to pgvector cosine similarity in live mode once a
    real embedding API is wired up.
    """
    if not (drug_name or icd10):
        return []

    key = (drug_name or "").lower()
    aliases = _drug_aliases().get(key, {key} if key else set())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, drug_name, diagnosis_code, rationale, receipt_url,
              CASE WHEN lower(drug_name) = ANY($1::text[]) THEN 2
                   WHEN diagnosis_code = $2                THEN 1
                   ELSE 0
              END AS rank
            FROM prior_auths
            WHERE status = 'approved'
              AND (lower(drug_name) = ANY($1::text[]) OR diagnosis_code = $2)
            ORDER BY rank DESC, created_at DESC
            LIMIT $3
            """,
            list(aliases),
            icd10,
            limit,
        )
    return [dict(r) for r in rows]
