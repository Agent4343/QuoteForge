"""Run Alembic migrations programmatically on startup (§18).

Invoked from the FastAPI lifespan for deployed environments. The advisory lock
that guards concurrent runs lives in ``alembic/env.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config

from alembic import command

logger = logging.getLogger("quoteforge.migrate")

_API_ROOT = Path(__file__).resolve().parents[1]  # .../apps/api


def _config() -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    return cfg


def run_upgrade() -> None:
    """Upgrade to head. Must be called from a thread with no running event loop
    (env.py uses asyncio.run); the lifespan dispatches it via asyncio.to_thread.
    """
    logger.info("Running database migrations to head")
    command.upgrade(_config(), "head")
    logger.info("Migrations complete")
