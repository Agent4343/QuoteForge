"""QuoteForge API entrypoint (§6, §18).

One service serves the API at ``/api/*`` and (in production) the built React
frontend as static files, falling back to ``index.html`` for SPA routes.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from quoteforge_api import __version__
from quoteforge_api.config import get_settings
from quoteforge_api.routes import auth, customers, dashboard, estimate, me, meta, quotes

logger = logging.getLogger("quoteforge.startup")
logging.basicConfig(level=get_settings().log_level.upper())

# Surfaced via /api/healthz so a degraded boot is visible instead of opaque.
STARTUP_STATE: dict[str, str] = {"data": "pending", "migrations": "skipped"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info("QuoteForge starting (env=%s)", settings.environment)

    # Load assemblies + price book. Wrapped so a data problem can't prevent the
    # app from binding — it's reported via /healthz instead of an opaque crash.
    try:
        from quoteforge_api.assemblies.loader import get_library
        from quoteforge_api.code_editions import get_code_matrix
        from quoteforge_api.pricebook import get_pricebook

        get_library()
        get_pricebook()
        get_code_matrix()
        STARTUP_STATE["data"] = "ok"
        logger.info("Assemblies, price book, and code matrix loaded")
    except Exception as exc:  # noqa: BLE001
        STARTUP_STATE["data"] = f"failed: {exc.__class__.__name__}"
        logger.exception("Failed to load assemblies/price book")

    # Run DB migrations on startup for deployed environments only (§18). In dev/
    # test, run `alembic upgrade head` (or docker compose) manually so the
    # stateless surfaces don't require a database.
    #
    # Migration failure is logged but NON-FATAL: the app still binds so the
    # healthcheck can pass and the error is visible in the logs, rather than the
    # container hanging/crashing on boot with no signal.
    if settings.is_deployed:
        from quoteforge_api.db_migrate import run_upgrade

        try:
            await asyncio.to_thread(run_upgrade)
            STARTUP_STATE["migrations"] = "ok"
        except Exception as exc:  # noqa: BLE001
            STARTUP_STATE["migrations"] = f"failed: {exc.__class__.__name__}"
            logger.exception("Startup migrations failed — serving in a degraded state")
    logger.info("Startup complete: %s", STARTUP_STATE)
    yield


app = FastAPI(title="QuoteForge API", version=__version__, lifespan=lifespan)

app.include_router(meta.router)
app.include_router(estimate.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(customers.router)
app.include_router(quotes.router)
app.include_router(dashboard.router)


# Static frontend (production). The Dockerfile builds apps/web into ./static.
_settings = get_settings()
_static_dir = _settings.data_dir.parent / "apps" / "api" / "static"
_assets_dir = _static_dir / "assets"
if _static_dir.is_dir() and (_static_dir / "index.html").is_file():

    @app.get("/")
    def _index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.exception_handler(404)
    async def _spa_fallback(request, exc):  # noqa: ANN001
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(_static_dir / "index.html")
else:
    logger.warning("No built frontend at %s; serving API only", _static_dir)
