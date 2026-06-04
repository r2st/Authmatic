"""The 4-verb ReAct loop.

Each iteration the planner picks ONE verb (READ-WEB / EXECUTE / VERIFY /
PERSIST) and produces an args dict. We dispatch, log to Postgres, push to
SSE, and feed the result back into the planner's history. Hard cap at 5
iterations + final ACTION. The ACTION step calls Rtrvr to file the form
on the payer portal.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import asyncpg

from .insforge_client import plan_next_step
from .persist import (
    append_event,
    fetch_plan_id_by_member_id,
    fetch_similar_approvals,
    link_patient_by_member_id,
    update_status,
)
from .phi import redact_phi
from .tools import execute, read_web, verify

MAX_ITERATIONS = 5

_logger = logging.getLogger("authmatic.agent.loop")

PLANNER_PROMPT = (
    Path(__file__).parent / "prompts" / "planner.txt"
).read_text()


async def run_agent(
    *,
    pool: asyncpg.Pool,
    run_id: str,
    pdf_bytes: bytes,
    on_event: Callable[[dict], Awaitable[None]],
) -> None:
    """Drive one full agent run for the given prior_auth row.

    Streams each step via `on_event` and writes durable state via persist.*.
    """
    history: list[dict] = [
        {"role": "system", "content": PLANNER_PROMPT},
        {
            "role": "user",
            "content": (
                "A prescription PDF has been uploaded. Begin the prior-auth filing "
                "workflow. Start with EXECUTE to parse the PDF."
            ),
        },
    ]

    parsed: dict = {}
    coverage_rule: dict | None = None
    rationale: str | None = None
    last_step_no = 0
    # Identity fields are frozen from the EXECUTE (PDF parse) step. Nothing
    # downstream — especially adversarial READ-WEB portal content — may alter
    # them before the final SUBMIT (ticket 0014 guardrail).
    frozen_identity: dict | None = None

    for step_no in range(1, MAX_ITERATIONS + 1):
        last_step_no = step_no
        plan = await plan_next_step(history)
        verb = plan["verb"]
        args = plan.get("args", {})

        # Forensic log of every planner decision (ticket 0014). We log the
        # chosen verb + one-line plan + the size of the (already PHI-redacted)
        # input that produced it — enough to reconstruct an injection attempt
        # without writing raw PHI to logs (ADR 0008).
        _logger.info(
            "planner.decision",
            extra={
                "run_id": run_id,
                "step_no": step_no,
                "verb": verb,
                "ready_to_submit": bool(plan.get("ready_to_submit")),
                "input_chars": sum(len(str(m.get("content", ""))) for m in history),
            },
        )

        t0 = time.perf_counter()

        try:
            if verb == "EXECUTE":
                tool_output = await execute.parse_prescription(pdf_bytes)
                parsed = tool_output
                # Snapshot the identity fields once, from the trusted parse.
                if frozen_identity is None:
                    frozen_identity = _identity(parsed)
            elif verb == "READ-WEB":
                # Resolve the patient's actual plan from the parsed member_id
                # so we look up the right payer's rules (Ozempic on
                # HF-CHOICE-PLUS, Humira on AET-OPEN-CHOICE, etc.). The
                # planner's default is UHC; the seeded patient overrides it.
                resolved_plan_id = (
                    await fetch_plan_id_by_member_id(pool, parsed.get("member_id"))
                    or args.get("plan_id", "")
                )
                tool_output = await read_web.fetch_coverage_rule(
                    drug_ndc=parsed.get("drug_ndc", args.get("drug_ndc", "")),
                    plan_id=resolved_plan_id,
                )
                args = {**args, "plan_id": resolved_plan_id}
                coverage_rule = tool_output
            elif verb == "VERIFY":
                packet = _build_packet(parsed, rationale)
                tool_output = await verify.scan_phi_exposure(
                    pool=pool, pa_id=run_id, packet=packet
                )
                if not tool_output.get("passed"):
                    raise RuntimeError(
                        f"Opsera flagged PHI fields: {tool_output.get('flagged_fields')}"
                    )
            elif verb == "PERSIST":
                # RAG step: pull similar approved PAs out of the
                # prior_auths table so the drafted rationale can cite them.
                similar = await fetch_similar_approvals(
                    pool,
                    drug_name=parsed.get("drug_name"),
                    icd10=parsed.get("icd10"),
                )
                rationale = args.get("rationale") or _draft_rationale(
                    parsed, coverage_rule, similar,
                )
                # If the PDF identified a known patient by member_id, swap
                # the prior_auths.patient_id over from the fallback row.
                resolved_patient_id = await link_patient_by_member_id(
                    pool, parsed.get("member_id")
                )
                await update_status(
                    pool=pool, pa_id=run_id,
                    status="pending",
                    drug_name=parsed.get("drug_name"),
                    drug_ndc=parsed.get("drug_ndc"),
                    dose=parsed.get("dose"),
                    diagnosis_code=parsed.get("icd10"),
                    rationale=rationale,
                    patient_id=resolved_patient_id,
                )
                tool_output = {
                    "persisted": True,
                    "linked_patient": resolved_patient_id is not None,
                    "similar_approvals": [
                        {
                            "ref": s["id"][:8],
                            "drug": s["drug_name"],
                            "icd10": s["diagnosis_code"],
                            "rank": s["rank"],
                        }
                        for s in similar
                    ],
                    "rationale": rationale[:120] + "…",
                }
            else:
                raise ValueError(f"Unknown verb: {verb}")

        except Exception as e:  # noqa: BLE001 - we log and stop the run
            elapsed = int((time.perf_counter() - t0) * 1000)
            ev = await append_event(
                pool, run_id, step_no, verb, plan["plan"],
                args, {"error": str(e)}, elapsed,
            )
            await on_event(ev)
            await update_status(pool=pool, pa_id=run_id, status="error")
            return

        elapsed = int((time.perf_counter() - t0) * 1000)
        ev = await append_event(
            pool, run_id, step_no, verb, plan["plan"], args, tool_output, elapsed,
        )
        await on_event(ev)

        # Feed the result back into the planner. PHI is redacted here (ADR
        # 0008): the planner reasons over masked identifiers — it never needs
        # the raw member_id / patient_name / SSN to pick the next verb. The
        # raw values stay in `parsed` (server-side only) for the actual form
        # submission. `_safe_for_history` also strips free text that could
        # carry a prompt-injection payload (ticket 0014).
        history.append({"role": "assistant", "content": str(plan)})
        history.append({
            "role": "tool",
            "content": (
                f"{verb} result: "
                f"<tool_output verb=\"{verb}\">{_safe_for_history(tool_output)}</tool_output>"
            ),
        })

        # Stop conditions: planner says we're ready to submit.
        if plan.get("ready_to_submit"):
            break

    # ─── Guardrail: identity must be unchanged since EXECUTE ─────────
    # Compare-and-fail (ticket 0014): the final SUBMIT must never proceed if
    # the drug NDC, diagnosis code, or member id drifted from what the trusted
    # PDF parse produced — e.g. coerced by adversarial READ-WEB portal content.
    if frozen_identity is not None and _identity(parsed) != frozen_identity:
        ev = await append_event(
            pool, run_id, last_step_no + 1, "ACTION",
            "Aborted submission — parsed identity fields changed after EXECUTE.",
            {"reason": "identity_drift"},
            {"error": "identity drift detected; refusing to submit"},
            0,
        )
        await on_event(ev)
        await update_status(pool=pool, pa_id=run_id, status="error")
        return

    # ─── ACTION: Rtrvr files the form ────────────────────────────────
    t0 = time.perf_counter()
    receipt_url = await read_web.submit_pa_form(
        pool=pool, pa_id=run_id,
        parsed=parsed,
        coverage_rule=coverage_rule,
        rationale=rationale or "",
    )
    elapsed = int((time.perf_counter() - t0) * 1000)
    ev = await append_event(
        pool, run_id, last_step_no + 1, "ACTION",
        "Submit the completed PA form to the payer portal and capture the receipt URL.",
        {"payer": coverage_rule.get("payer") if coverage_rule else "UHC"},
        {"receipt_url": receipt_url},
        elapsed,
    )
    await on_event(ev)
    await update_status(pool=pool, pa_id=run_id, status="submitted", receipt_url=receipt_url)


#: Patient/clinical facts that come ONLY from the trusted PDF parse and must
#: never be mutated by downstream (adversarial) tool output (ticket 0014).
_IDENTITY_FIELDS = ("member_id", "drug_ndc", "icd10")


def _identity(parsed: dict) -> dict:
    """The frozen-from-EXECUTE identity fields, for compare-and-fail."""
    return {k: parsed.get(k) for k in _IDENTITY_FIELDS}


def _safe_for_history(tool_output) -> dict | str:
    """Redact PHI before a tool result re-enters the planner's chat history.

    The planner runs on a third-party LLM (OpenRouter). Per ADR 0008, raw
    PHI must not leave our trust boundary beyond what is strictly required —
    and the planner's job (pick the next verb) never requires raw
    identifiers. Returns the input unchanged if it isn't a dict.
    """
    if isinstance(tool_output, dict):
        return redact_phi(tool_output)
    return tool_output


def _build_packet(parsed: dict, rationale: str | None) -> dict:
    # Pass through every parsed field. Opsera VERIFY filters against the
    # allowlist on its end — over-disclosure (e.g. patient_ssn) gets flagged
    # there, not here. The whole point of the safety layer is to catch what
    # the agent forgets to drop.
    return {
        "drug_name": parsed.get("drug_name"),
        "drug_ndc": parsed.get("drug_ndc"),
        "dose": parsed.get("dose"),
        "diagnosis_code": parsed.get("icd10"),
        "member_id": parsed.get("member_id"),
        "full_name": parsed.get("patient_name"),
        "patient_ssn": parsed.get("patient_ssn"),
        "rationale": rationale,
    }


def _draft_rationale(
    parsed: dict,
    coverage_rule: dict | None,
    similar: list[dict] | None = None,
) -> str:
    """In production the planner LLM drafts this. For the demo path we use a
    deterministic template so the demo never produces gibberish. If similar
    past-approved PAs were found, cite them as precedent."""
    drug = parsed.get("drug_name", "the requested medication")
    dx = parsed.get("icd10", "the clinical diagnosis")
    criteria = (coverage_rule or {}).get(
        "criteria_text", "the plan's coverage criteria"
    )
    base = (
        f"Patient meets medical-necessity criteria for {drug}. "
        f"Diagnosis {dx} satisfies {criteria}. First-line alternatives "
        f"have been tried and documented in the chart."
    )
    if similar:
        precedents = "; ".join(
            f"{s['drug_name']} for {s['diagnosis_code']} (ref {s['id'][:8]})"
            for s in similar[:2]
        )
        base += f" Precedent: {len(similar)} similar approved PAs on file — {precedents}."
    return base
