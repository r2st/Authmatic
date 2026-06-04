"""READ-WEB verb — Rtrvr.ai.

Two operations:
  1. fetch_coverage_rule — pull the live PA criteria for (drug, plan)
  2. submit_pa_form      — fill + submit the form on the payer portal

Both go through Rtrvr's /agent endpoint. RTRVR_MODE picks cloud vs
extension; this codepath assumes "cloud". When DEMO_FIXTURE_MODE is true,
we replay from assets/fixtures/ instead of hitting the network.
"""

from __future__ import annotations

import json
import os

import asyncpg
import httpx

from ..settings import get_settings

RTRVR_BASE = "https://api.rtrvr.ai"


async def ping() -> dict:
    """Used by /api/smoke."""
    s = get_settings()
    if s.demo_fixture_mode:
        return {"ok": True, "mode": "fixture"}
    if not s.rtrvr_api_key:
        return {"ok": False, "error": "RTRVR_API_KEY not set"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{RTRVR_BASE}/health",
            headers={"Authorization": f"Bearer {s.rtrvr_api_key}"},
        )
        return {"ok": r.status_code == 200, "status": r.status_code}


async def fetch_coverage_rule(drug_ndc: str, plan_id: str) -> dict:
    s = get_settings()

    if s.demo_fixture_mode:
        return _lookup_coverage_rule(drug_ndc, plan_id)

    task = (
        "Log into the UHC provider portal and find the prior-auth "
        f"criteria for drug NDC {drug_ndc} under plan {plan_id}. "
        "Return JSON: {payer, covered, requires_pa, criteria_text}."
    )
    return await _agent_call(task, schema={
        "payer": "string",
        "covered": "boolean",
        "requires_pa": "boolean",
        "criteria_text": "string",
    })


async def submit_pa_form(
    *,
    pool: asyncpg.Pool,
    pa_id: str,
    parsed: dict,
    coverage_rule: dict | None,
    rationale: str,
) -> str:
    """Fill + submit the form. Returns the receipt URL."""
    s = get_settings()

    if s.demo_fixture_mode:
        # Local receipt page so the demo can't fail on conference WiFi.
        return f"{s.web_base_url.rstrip('/')}/receipt/{pa_id}"

    # Hydrate patient fields from Postgres (we don't put PHI in the planner).
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.full_name, p.dob, p.member_id
            FROM prior_auths pa JOIN patients p ON p.id = pa.patient_id
            WHERE pa.id = $1
            """,
            pa_id,
        )

    task = (
        "Open the UHC prior-authorization form. Fill in: "
        f"patient={row['full_name']}, dob={row['dob']}, "
        f"member_id={row['member_id']}, drug={parsed.get('drug_name')}, "
        f"dose={parsed.get('dose')}, diagnosis={parsed.get('icd10')}, "
        f"medical_necessity={rationale!r}. Submit. "
        "Return the confirmation URL."
    )
    result = await _agent_call(task, schema={"receipt_url": "string"})
    return result["receipt_url"]


async def _agent_call(task: str, *, schema: dict) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{RTRVR_BASE}/agent",
            json={"task": task, "schema": schema, "mode": s.rtrvr_mode},
            headers={"Authorization": f"Bearer {s.rtrvr_api_key}"},
        )
        r.raise_for_status()
    return r.json()["output"]


def _fixture(name: str, *, key: str | None = None) -> dict:
    s = get_settings()
    path = os.path.join(s.fixtures_path, name)
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and key in data:
        return data[key]
    if isinstance(data, dict) and "default" in data:
        return data["default"]
    return data


def _lookup_coverage_rule(drug_ndc: str, plan_id: str) -> dict:
    """Find a coverage rule for (drug_ndc, plan_id) across both fixture sources.

    Lookup order:
      1. uhc-rules.json keyed by `<ndc>|<plan>` (the simple Lisinopril/
         Metformin fixtures).
      2. mock_data.json's payer_coverage_rules (Ozempic/Humira/Dupixent
         across HealthFirst + Aetna).
      3. uhc-rules.json's `default` (generic fallback).

    Always returns the shape downstream code expects:
        {payer, covered, requires_pa, criteria_text}
    """
    key = f"{drug_ndc}|{plan_id}"
    s = get_settings()

    # 1. Targeted hit in uhc-rules.json.
    uhc_path = os.path.join(s.fixtures_path, "uhc-rules.json")
    with open(uhc_path) as f:
        uhc = json.load(f)
    if isinstance(uhc, dict) and key in uhc:
        return uhc[key]

    # 2. mock_data.json — keyed indirectly via drug_id → ndc.
    mock = _load_mock_coverage_rules()
    if key in mock:
        return mock[key]

    # 3. uhc-rules.json default.
    if isinstance(uhc, dict) and "default" in uhc:
        return uhc["default"]
    return uhc


_MOCK_RULES_CACHE: dict[str, dict] | None = None


def _load_mock_coverage_rules() -> dict[str, dict]:
    """Build a (ndc|plan_id) → coverage-rule map from mock_data.json once.

    Projects to the same {payer, covered, requires_pa, criteria_text} shape
    the rest of the app expects.
    """
    global _MOCK_RULES_CACHE
    if _MOCK_RULES_CACHE is not None:
        return _MOCK_RULES_CACHE

    s = get_settings()
    path = os.path.join(s.fixtures_path, "mock_data.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        _MOCK_RULES_CACHE = {}
        return _MOCK_RULES_CACHE

    # Build cross-reference maps.
    drug_id_to_ndc = {d["id"]: d["ndc"] for d in data.get("drugs", [])}
    insurer_id_to_name = {}
    for ins_key in ("insurer", "second_insurer"):
        ins = data.get(ins_key)
        if ins:
            insurer_id_to_name[ins["id"]] = ins["name"]

    rules: dict[str, dict] = {}
    for r in data.get("payer_coverage_rules", []):
        ndc = drug_id_to_ndc.get(r["drug_id"])
        if not ndc:
            continue
        key = f"{ndc}|{r['plan_id']}"
        rules[key] = {
            "payer": insurer_id_to_name.get(r["insurer_id"], r["insurer_id"]),
            "covered": r["covered"],
            "requires_pa": r["requires_pa"],
            "criteria_text": r.get("criteria_text", ""),
        }

    _MOCK_RULES_CACHE = rules
    return rules
