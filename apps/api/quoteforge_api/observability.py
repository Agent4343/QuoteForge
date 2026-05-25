"""Logging and error reporting setup (§18 structured logging, §19 Sentry).

Structured JSON logs go to stdout (one object per line) so the host can ingest
them; uvicorn's access/error logs are routed through the same handler. Sentry is
initialised only when SENTRY_DSN is configured.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from quoteforge_api.config import Settings


class JsonFormatter(logging.Formatter):
    """Minimal, dependency-free JSON log formatter (one object per line)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Route uvicorn's own loggers through the root handler so all output is uniform.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


def init_sentry(settings: Settings) -> bool:
    """Initialise Sentry if a DSN is configured. Returns True if enabled."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger("quoteforge.startup").warning(
            "SENTRY_DSN set but sentry-sdk is not installed; skipping."
        )
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    return True
