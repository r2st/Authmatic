"""Agent structured-logging tests (ticket 0011)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.logging import JsonFormatter  # noqa: E402


def _format(name="t", level=logging.INFO, msg="event.name", **extra):
    rec = logging.LogRecord(name, level, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return json.loads(JsonFormatter().format(rec))


def test_emits_valid_json_with_core_fields():
    out = _format()
    assert out["service"] == "authmatic-agent"
    assert out["level"] == "info"
    assert out["event"] == "event.name"
    assert "ts" in out


def test_surfaces_extra_correlation_fields():
    out = _format(msg="planner.decision", run_id="r1", clinic_id="c1", verb="EXECUTE")
    assert out["run_id"] == "r1"
    assert out["clinic_id"] == "c1"
    assert out["verb"] == "EXECUTE"


def test_includes_exception_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
        out = json.loads(JsonFormatter().format(rec))
    assert out["level"] == "error"
    assert "boom" in out["exc"]
