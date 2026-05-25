"""Health and reference-data routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.config import get_settings
from quoteforge_api.services import logos

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness + DB connectivity check (§18).

    Deliberately takes NO DB-session dependency: a bad/unparseable DATABASE_URL
    raises when the engine is built, which during dependency injection would
    500 before any handler code runs. We build the connection inside a broad
    try/except so the healthcheck always returns 200 (degraded when the DB is
    unreachable or misconfigured) and reports what's wrong.
    """
    from quoteforge_api.main import STARTUP_STATE

    db_ok = True
    db_error = None
    try:
        from quoteforge_api.db import get_sessionmaker

        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = exc.__class__.__name__
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "db_error": db_error,
        "data": STARTUP_STATE.get("data", "unknown"),
        "migrations": STARTUP_STATE.get("migrations", "unknown"),
        "environment": get_settings().environment,
    }


@router.get("/code-editions")
def code_editions() -> dict:
    """Per-province electrical-code matrix (regulator, permit model, editions,
    transition windows). Source of truth: data/code_editions.yaml."""
    from quoteforge_api.code_editions import get_code_matrix

    matrix = get_code_matrix()
    return {
        "provinces": {
            p.value: pc.model_dump(mode="json") for p, pc in matrix.all().items()
        }
    }


@router.get("/logos/{user_id}")
def get_logo(user_id: uuid.UUID) -> FileResponse:
    """Serve a contractor logo from the volume. Public (logos appear on quotes)."""
    path = logos.logo_path(user_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No logo")
    return FileResponse(path, media_type=logos.content_type_for(path))


@router.get("/assemblies")
def list_assemblies() -> dict:
    """Reference list of assemblies available to the engine.

    Includes draft assemblies (with a flag) since none are electrician-reviewed
    yet (§8); the LLM index — separate — only exposes reviewed ones.
    """
    lib = get_library()
    return {
        "assemblies": [
            {
                "id": a.id,
                "category": a.category.value,
                "names": {"en": a.names.en, "fr": a.names.fr},
                "status": a.status.value,
                "parameters": {
                    name: {
                        "type": p.type.value,
                        "default": p.default,
                        "values": p.values,
                        "sensitivity": p.sensitivity.value,
                    }
                    for name, p in a.parameters.items()
                },
            }
            for a in lib.all()
        ]
    }
