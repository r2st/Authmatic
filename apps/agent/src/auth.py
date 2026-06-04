"""Service-to-service auth for the agent API (ticket 0005).

The agent service is called only by the Authmatic web backend, not by
browsers. We authenticate with a shared bearer token (`AGENT_SERVICE_TOKEN`)
rather than a user session. Use as a FastAPI dependency:

    @app.post("/api/run", dependencies=[Depends(require_service_token)])

`/healthz` and `/readyz` stay public (liveness/readiness probes).

Posture:
  - token set   → constant-time compare; mismatch/missing → 401.
  - token unset → allowed ONLY when not in production (dev convenience);
                  in production a missing token fails closed (503), so a
                  misconfigured deploy can't run wide open.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def _is_production() -> bool:
    return os.environ.get("INSFORGE_ENV", "development").lower() == "production"


def require_service_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AGENT_SERVICE_TOKEN", "").strip()

    if not expected:
        if _is_production():
            # Fail closed: never run unauthenticated in prod.
            raise HTTPException(status_code=503, detail="Agent auth not configured")
        return  # dev convenience only

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    presented = authorization[len("Bearer ") :].strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")
