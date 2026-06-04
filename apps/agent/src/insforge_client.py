"""Planner LLM client.

Calls OpenRouter directly (the OpenAI-compatible upstream behind InsForge's
AI gateway). Authenticated with `OPENROUTER_API_KEY`, provisioned via
`npx @insforge/cli ai setup --env-file .env`. Server-only.

The planner is forced into strict JSON output so we can parse the next
verb without prose drift.
"""

from __future__ import annotations

import json

import httpx

from .settings import get_settings


async def plan_next_step(history: list[dict]) -> dict:
    """Ask the planner for the next verb + args. Returns a dict shaped:

      {
        "plan": "<one sentence>",
        "verb": "READ-WEB|EXECUTE|VERIFY|PERSIST",
        "args": {...},
        "ready_to_submit": false
      }

    In DEMO_FIXTURE_MODE, returns a scripted plan so the demo loop runs
    end-to-end without an Insforge API key. Retries once on malformed JSON
    in live mode. On the second failure, raises.
    """
    s = get_settings()

    if s.demo_fixture_mode:
        return _fixture_plan(history)

    url = f"{s.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": s.insforge_model,
        "messages": history,
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {s.openrouter_api_key}",
        # OpenRouter requires HTTP-Referer + X-Title for attribution; the
        # project URL doubles as a stable identifier here.
        "HTTP-Referer": s.insforge_project_url or "https://authmatic.local",
        "X-Title": "Authmatic Planner",
    }

    for attempt in (1, 2):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            history.append({
                "role": "system",
                "content": "Your last reply was not valid JSON. Reply ONLY with a JSON object.",
            })
            continue

        # Light shape validation.
        if "verb" not in data or "plan" not in data:
            if attempt == 2:
                raise ValueError(f"Planner returned malformed shape: {data}")
            history.append({
                "role": "system",
                "content": "Your last reply must contain both 'verb' and 'plan'. Try again.",
            })
            continue

        data.setdefault("args", {})
        data.setdefault("ready_to_submit", False)
        return data

    raise RuntimeError("unreachable")  # pragma: no cover


# ─── Fixture-mode planner ────────────────────────────────────────────────
#
# A deterministic 4-step script the loop runs when DEMO_FIXTURE_MODE=true.
# Order matches the planner.txt rules: EXECUTE → READ-WEB → PERSIST → VERIFY,
# then loop.py fires the final ACTION (Rtrvr submit) on its own.
_FIXTURE_SCRIPT = [
    {
        "verb": "EXECUTE",
        "plan": "Parse the prescription PDF in a Daytona sandbox to extract drug, NDC, dose, "
        "and ICD-10.",
        "args": {},
    },
    {
        "verb": "READ-WEB",
        "plan": "Fetch the live UHC coverage rule for the extracted drug + member plan "
        "via Rtrvr.",
        "args": {"plan_id": "UHC-CHOICE-PLUS"},
    },
    {
        "verb": "PERSIST",
        "plan": "Write the structured fields and a drafted medical-necessity rationale "
        "to Postgres.",
        "args": {},
    },
    {
        "verb": "VERIFY",
        "plan": "Scan the outgoing packet via Opsera MCP for PHI over-disclosure "
        "before submission.",
        "args": {},
        "ready_to_submit": True,
    },
]


def _fixture_plan(history: list[dict]) -> dict:
    # Count assistant turns so far → that's how many steps we've already taken.
    taken = sum(1 for m in history if m.get("role") == "assistant")
    if taken >= len(_FIXTURE_SCRIPT):
        # Shouldn't happen — the VERIFY step sets ready_to_submit=True and
        # loop.py breaks out. Guard just in case.
        return {**_FIXTURE_SCRIPT[-1], "ready_to_submit": True}
    step = dict(_FIXTURE_SCRIPT[taken])
    step.setdefault("args", {})
    step.setdefault("ready_to_submit", False)
    return step
