"""Tests for upload hardening (ticket 0013).

Self-contained: drives the async `read_pdf_upload` via asyncio.run so it runs
under plain pytest without pytest-asyncio (the broader test harness is 0010).
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.upload import (  # noqa: E402
    MAX_PDF_BYTES,
    read_pdf_upload,
    sanitize_filename,
    storage_key,
)


def _upload(data: bytes, filename: str = "rx.pdf") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data))


def _read(data: bytes, content_length: str | None = None) -> bytes:
    return asyncio.run(read_pdf_upload(_upload(data), content_length))


# ── sanitize_filename ────────────────────────────────────────────────
def test_sanitize_strips_path_traversal():
    assert sanitize_filename("../../../etc/passwd") == "passwd"


def test_sanitize_restricts_charset():
    assert sanitize_filename("rx report (1).pdf") == "rx_report__1_.pdf"


def test_sanitize_never_empty():
    assert sanitize_filename("") == "upload.pdf"
    assert sanitize_filename(None) == "upload.pdf"


def test_sanitize_caps_length():
    assert len(sanitize_filename("a" * 500)) == 100


# ── storage_key ──────────────────────────────────────────────────────
def test_storage_key_uses_clinic_and_run_not_filename():
    key = storage_key("clinic-1", "run-9", "../../evil.pdf")
    assert key == "charts/clinic-1/run-9/evil.pdf"


# ── read_pdf_upload ──────────────────────────────────────────────────
def test_accepts_valid_pdf():
    data = b"%PDF-1.4\n" + b"clean body"
    assert _read(data) == data


def test_rejects_non_pdf_magic():
    with pytest.raises(HTTPException) as e:
        _read(b"MZ\x90\x00 not a pdf")
    assert e.value.status_code == 400


def test_rejects_oversize_by_content_length():
    with pytest.raises(HTTPException) as e:
        _read(b"%PDF-1.4 small", content_length=str(MAX_PDF_BYTES + 1))
    assert e.value.status_code == 413


def test_rejects_oversize_by_streaming_guard():
    big = b"%PDF-1.4\n" + b"x" * (MAX_PDF_BYTES + 10)
    with pytest.raises(HTTPException) as e:
        _read(big)  # no content-length header → streaming cap must catch it
    assert e.value.status_code == 413


def test_rejects_embedded_javascript():
    with pytest.raises(HTTPException) as e:
        _read(b"%PDF-1.4\n/OpenAction << /JS (app.alert\\(1\\)) >>")
    assert e.value.status_code == 400
