"""Upload hardening for the agent PDF intake (ticket 0013).

Closes three bugs in the old `post_run`:
  1. DoS via huge uploads — `await pdf.read()` with no cap can OOM the worker.
  2. MIME spoofing — the old check trusted the client `content_type` header.
  3. Path traversal — the raw `pdf.filename` was used in the storage key.

Use `read_pdf_upload()` to size-cap + magic-byte-validate the body, and
`sanitize_filename()` + `storage_key()` to build a safe, collision-free key.
"""

from __future__ import annotations

import re

from fastapi import HTTPException, UploadFile

# 20 MB hard cap. Prescriptions are a few hundred KB; 20 MB is generous.
MAX_PDF_BYTES = 20 * 1024 * 1024
_CHUNK = 1 << 20  # 1 MB
_PDF_MAGIC = b"%PDF-"

# PDF dictionary keys that trigger code execution on open/interaction. A
# prescription PDF never needs these, so their presence is a strong signal of
# a weaponized file — reject (ticket 0013). This is a cheap structural check,
# not a substitute for AV scanning (see ADR 0010).
_ACTIVE_CONTENT_MARKERS = (
    b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch", b"/EmbeddedFile",
)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(name: str | None) -> str:
    """Reduce an attacker-supplied filename to a safe basename.

    Strips any path components, restricts to [A-Za-z0-9._-], collapses leading
    dots (no hidden/`..` names), caps length, and never returns empty.
    """
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = _SAFE_NAME_RE.sub("_", base).lstrip(".")
    base = base[:100]
    return base or "upload.pdf"


def storage_key(clinic_id: str, run_id: str, filename: str) -> str:
    """Build the object-storage key. Uniqueness comes from clinic_id + run_id,
    NEVER from the untrusted filename."""
    safe_clinic = _SAFE_NAME_RE.sub("_", clinic_id or "unknown")
    return f"charts/{safe_clinic}/{run_id}/{sanitize_filename(filename)}"


async def read_pdf_upload(pdf: UploadFile, content_length: str | None = None) -> bytes:
    """Stream the upload with a hard size cap and confirm it is really a PDF.

    Raises 413 if oversize, 400 if the body isn't a PDF (magic bytes), so a
    renamed `.exe` or a 5 GB stream can't get through.
    """
    # Cheap early reject on a declared Content-Length (don't trust it alone).
    if content_length is not None:
        try:
            if int(content_length) > MAX_PDF_BYTES:
                raise HTTPException(status_code=413, detail="PDF exceeds 20 MB limit")
        except ValueError:
            pass

    buf = bytearray()
    while True:
        chunk = await pdf.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds 20 MB limit")

    if not bytes(buf[: len(_PDF_MAGIC)]) == _PDF_MAGIC:
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    data = bytes(buf)
    marker = next((m for m in _ACTIVE_CONTENT_MARKERS if m in data), None)
    if marker is not None:
        raise HTTPException(
            status_code=400,
            detail=f"PDF contains active content ({marker.decode()}) and was rejected",
        )

    return data
