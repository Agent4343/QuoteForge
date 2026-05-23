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

logging.basicConfig(level=get_settings().log_level.upper())


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load and validate assemblies + price book at startup (§7); fail fast on bad data.
    from quoteforge_api.assemblies.loader import get_library
    from quoteforge_api.pricebook import get_pricebook

    get_library()
    get_pricebook()

    # Run DB migrations on startup for deployed environments only (§18). In dev/
    # test, run `alembic upgrade head` (or docker compose) manually so the
    # stateless surfaces don't require a database.
    if get_settings().environment in {"prod", "staging"}:
        from quoteforge_api.db_migrate import run_upgrade

        await asyncio.to_thread(run_upgrade)
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
if _static_dir.is_dir():

    @app.get("/")
    def _index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.exception_handler(404)
    async def _spa_fallback(request, exc):  # noqa: ANN001
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(_static_dir / "index.html")
