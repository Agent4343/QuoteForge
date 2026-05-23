"""Health and reference-data routes."""

from __future__ import annotations

from fastapi import APIRouter

from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.config import get_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/healthz")
def healthz() -> dict:
    """Liveness check (§18). DB connectivity is added when the DB layer lands."""
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}


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
