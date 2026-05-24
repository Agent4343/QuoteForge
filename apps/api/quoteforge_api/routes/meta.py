"""Health and reference-data routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.auth.dependencies import SessionDep
from quoteforge_api.config import get_settings
from quoteforge_api.services import logos

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/healthz")
async def healthz(session: SessionDep) -> dict:
    """Liveness + DB connectivity check (§18)."""
    from quoteforge_api.main import STARTUP_STATE

    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "data": STARTUP_STATE.get("data", "unknown"),
        "migrations": STARTUP_STATE.get("migrations", "unknown"),
        "environment": get_settings().environment,
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
