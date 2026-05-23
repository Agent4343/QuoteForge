"""Health and reference-data routes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.auth.dependencies import SessionDep
from quoteforge_api.config import get_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/healthz")
async def healthz(session: SessionDep) -> dict:
    """Liveness + DB connectivity check (§18)."""
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "environment": get_settings().environment,
    }


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
