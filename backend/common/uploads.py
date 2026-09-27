"""
Server side upload policy.

Extension, declared content type and file signature must all agree, and the
payload must be sniffed rather than trusted. Files are stored under a
non-guessable key so that a media path can never be derived from the original
name.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename

# extension -> (allowed declared MIME types, expected byte signatures)
ALLOWED_TYPES: dict[str, tuple[set[str], tuple[bytes, ...]]] = {
    "pdf": ({"application/pdf"}, (b"%PDF-",)),
    "png": ({"image/png"}, (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ({"image/jpeg"}, (b"\xff\xd8\xff",)),
    "jpeg": ({"image/jpeg"}, (b"\xff\xd8\xff",)),
    "webp": ({"image/webp"}, (b"RIFF",)),
    "txt": ({"text/plain"}, ()),
    "csv": ({"text/csv", "text/plain", "application/csv"}, ()),
    "doc": (
        {"application/msword"},
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ),
    "docx": (
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        (b"PK\x03\x04",),
    ),
    "xls": ({"application/vnd.ms-excel"}, (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
    "xlsx": (
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        (b"PK\x03\x04",),
    ),
}

# The declared type is optional for a few formats where browsers are unreliable.
OPTIONAL_DECLARED_MIME = {"txt", "csv", "jpg", "jpeg"}


@dataclass(frozen=True)
class ValidatedUpload:
    storage_name: str
    original_name: str
    content_type: str
    size: int
    checksum: str


def validate_upload(uploaded_file, *, field: str = "file") -> ValidatedUpload:
    if uploaded_file is None:
        raise ValidationError({field: ["This field is required."]})

    name = uploaded_file.name or ""
    extension = os.path.splitext(name)[1].lower().lstrip(".")
    if not extension:
        raise ValidationError({field: ["A file extension is required."]})

    allowed = {e.lower() for e in settings.ALLOWED_UPLOAD_EXTENSIONS}
    if extension not in allowed:
        raise ValidationError(
            {field: [f"Files of type '{extension}' are not accepted."]}
        )
    if extension not in ALLOWED_TYPES:
        raise ValidationError({field: [f"Files of type '{extension}' are not accepted."]})

    size = getattr(uploaded_file, "size", 0) or 0
    max_bytes = settings.MAX_UPLOAD_BYTES
    if size <= 0:
        raise ValidationError({field: ["The uploaded file is empty."]})
    if size > max_bytes:
        limit_mb = round(max_bytes / (1024 * 1024), 1)
        raise ValidationError({field: [f"Files must be {limit_mb} MB or smaller."]})

    declared = (getattr(uploaded_file, "content_type", "") or "").lower().split(";")[0].strip()
    allowed_mimes, signatures = ALLOWED_TYPES[extension]
    if declared and extension not in OPTIONAL_DECLARED_MIME and declared not in allowed_mimes:
        raise ValidationError(
            {field: ["The file content does not match its file type."]}
        )
    if not declared:
        declared = next(iter(sorted(allowed_mimes)))

    payload = uploaded_file.read(4096)
    if signatures and not any(payload.startswith(sig) for sig in signatures):
        raise ValidationError(
            {field: ["The file content does not match its file type."]}
        )

    uploaded_file.seek(0)
    checksum = hashlib.sha256(uploaded_file.read()).hexdigest()
    uploaded_file.seek(0)

    safe_stem = get_valid_filename(os.path.splitext(name)[0])[:60] or "upload"
    key = f"{uuid.uuid4().hex}/{safe_stem}.{extension}"
    default_storage.save(key, uploaded_file)

    return ValidatedUpload(
        storage_name=key,
        original_name=Path(name).name[:180],
        content_type=declared,
        size=size,
        checksum=checksum,
    )
