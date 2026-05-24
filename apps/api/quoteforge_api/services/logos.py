"""Contractor logo storage on the Railway volume (§23.6 decision).

Logos are written to ``logo_storage_dir`` keyed by user id and served back via
``GET /api/logos/{user_id}``. The PDF renderer resolves the on-disk path so
WeasyPrint reads the bytes directly (a relative API URL wouldn't resolve).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from quoteforge_api.config import get_settings

# Accepted upload content types -> file extension.
ALLOWED_TYPES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "image/webp": "webp",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB

_CONTENT_TYPE_BY_EXT = {ext: ct for ct, ext in ALLOWED_TYPES.items()}


def _dir() -> Path:
    d = get_settings().logo_storage_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_logo(user_id: uuid.UUID, content_type: str, data: bytes) -> str:
    """Persist a logo and return its public URL path. Raises ValueError on a bad
    content type or oversized file."""
    ext = ALLOWED_TYPES.get(content_type)
    if ext is None:
        raise ValueError(f"unsupported image type: {content_type}")
    if len(data) > MAX_LOGO_BYTES:
        raise ValueError("logo exceeds the 2 MB limit")
    # One logo per user; remove any prior extension before writing the new one.
    for existing in _dir().glob(f"{user_id}.*"):
        existing.unlink()
    (_dir() / f"{user_id}.{ext}").write_bytes(data)
    return f"/api/logos/{user_id}"


def logo_path(user_id: uuid.UUID) -> Path | None:
    matches = sorted(_dir().glob(f"{user_id}.*"))
    return matches[0] if matches else None


def content_type_for(path: Path) -> str:
    return _CONTENT_TYPE_BY_EXT.get(path.suffix.lstrip("."), "application/octet-stream")
