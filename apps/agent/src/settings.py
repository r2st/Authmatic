"""Centralized config — every sponsor key + fixture-mode flag."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Insforge backend ──
    # api_key here is reserved for direct InsForge backend calls (DB/storage/
    # edge-fn admin) — NOT the planner LLM. The planner uses OpenRouter
    # directly via the dedicated key below. Provisioned via
    # `npx @insforge/cli current` / `link`. Leave blank in fixture mode.
    insforge_api_key: str = ""
    insforge_project_url: str = ""
    insforge_db_url: str = "postgres://postgres:postgres@localhost:5432/postgres"

    # ── Planner LLM (OpenRouter via InsForge AI gateway) ──
    # Provisioned by `npx @insforge/cli ai setup --env-file .env`. Server-only.
    # Model name uses OpenRouter's slug convention, e.g.
    # "meta-llama/llama-3.1-70b-instruct".
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    insforge_model: str = "meta-llama/llama-3.1-70b-instruct"

    # Daytona
    daytona_api_key: str = ""
    daytona_snapshot_id: str = "authmatic-v1"

    # Rtrvr.ai
    rtrvr_api_key: str = ""
    rtrvr_mode: str = "cloud"  # "cloud" | "extension" — PICK ONE

    # Opsera
    opsera_mcp_url: str = "https://mcp.opsera.io/mcp"
    opsera_token: str = ""

    # ── Payer integration ──
    # When true, the MockPayerAdapter is used regardless of other config.
    # Automatically true when demo_fixture_mode is on.
    mock_payer: bool = True
    # CoverMyMeds credentials (the dominant ePA network).
    covermymeds_api_key: str = ""
    covermymeds_api_base: str = "https://api.covermymeds.com"

    # Where the user's browser hits this app — used to build the receipt
    # URL that the payer-portal step returns. In real production this would
    # be the payer's confirmation URL, not ours.
    web_base_url: str = "http://localhost:3000"

    # The prior-auth portal the agent drives when NOT in fixture mode. Defaults
    # to OUR OWN mock portal — it must NEVER default to a real payer. Targeting
    # a real/sandbox payer requires explicitly setting PA_PORTAL_URL to a
    # sanctioned URL (tickets 0025/0031). This prevents a stray
    # DEMO_FIXTURE_MODE=false from firing the agent at a production payer.
    pa_portal_url: str = "http://localhost:3000/portal/healthfirst/prior-auth"

    # Environment (ticket 0019): development | staging | production.
    authmatic_env: str = "development"

    # Demo
    demo_fixture_mode: bool = False
    # In-process agent shortcut (demo): run the pipeline inside the request
    # instead of the real agent service. Must be off in production (ticket 0019).
    use_inprocess_agent: bool = False
    fixtures_path: str = os.environ.get(
        "FIXTURES_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "fixtures"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.authmatic_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def assert_safe_for_production(s: Settings) -> None:
    """Fail fast if demo shortcuts are enabled in production (ticket 0019)."""
    if s.is_production and s.demo_fixture_mode:
        raise RuntimeError(
            "Refusing to start: DEMO_FIXTURE_MODE is on in production. "
            "It replays fixtures instead of processing real input."
        )
    if s.is_production and s.use_inprocess_agent:
        raise RuntimeError(
            "Refusing to start: USE_INPROCESS_AGENT is on in production. "
            "The real agent service must handle production runs."
        )
