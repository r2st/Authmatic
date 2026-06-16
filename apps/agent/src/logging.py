"""Structured JSON logging for the agent service (ticket 0011).

Dependency-free: stdlib `logging` + a JSON formatter to stdout, level from
`LOG_LEVEL`. Every line carries timestamp, level, service, logger, message,
and any correlation fields passed via `extra=` (request_id, clinic_id,
run_id) — e.g. loop.py's `planner.decision` events.

PHI must never be passed as a field value; use `src.phi.redact_phi` first
(ADR 0008). This formatter does not itself redact — it logs what it's given —
so callers redact at the call site, exactly as loop.py does.

`structlog` is a drop-in upgrade if richer processors are wanted later; the
call sites (`logging.getLogger(...).info(event, extra=...)`) don't change.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime

# Per-request correlation id (ticket 0021), set by the FastAPI middleware from
# the inbound X-Request-ID and surfaced on every log line within the request.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Fields the stdlib LogRecord always has — everything else in __dict__ is a
# caller-supplied `extra` and gets surfaced as a structured field.
_STD = set(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": "authmatic-agent",
            "logger": record.name,
            "event": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid and "request_id" not in record.__dict__:
            payload["request_id"] = rid
        for k, v in record.__dict__.items():
            if k not in _STD and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Install the JSON handler on the root logger. Idempotent."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(level)
    # Replace any existing handlers so we don't double-log.
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
