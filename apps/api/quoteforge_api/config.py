"""Application configuration (§18 environment variables).

Secrets and deployment knobs come from the environment. Data paths default to
the version-controlled ``/data`` directory at the repo root but can be
overridden (e.g. in a container image where data is copied elsewhere).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../apps/api/quoteforge_api/config.py -> repo root is three parents up.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# libpq DSN query params asyncpg doesn't accept; handled via connect_args instead.
_SSL_MODES_REQUIRING_TLS = {"require", "verify-ca", "verify-full", "prefer", "allow"}


def normalize_async_db_url(raw: str) -> tuple[str, dict]:
    """Return an asyncpg-compatible URL + connect_args.

    Managed hosts (Railway, Heroku) hand out ``postgres://`` / ``postgresql://``
    URLs, but our async engine needs the ``postgresql+asyncpg`` driver. We also
    move libpq-only query params (``sslmode``, ``channel_binding``) out of the
    DSN into asyncpg ``connect_args`` so the connection doesn't error.
    """
    url = raw
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    connect_args: dict = {}
    parts = urlsplit(url)
    if parts.query and parts.scheme.startswith("postgresql+asyncpg"):
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        sslmode = q.pop("sslmode", None)
        q.pop("channel_binding", None)
        if sslmode in _SSL_MODES_REQUIRING_TLS:
            connect_args["ssl"] = True
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
    return url, connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    environment: str = Field(default="dev")  # dev | staging | prod
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="postgresql+asyncpg://localhost/quoteforge")
    jwt_secret: str = Field(default="dev-insecure-change-me")
    anthropic_api_key: str = Field(default="")
    # LLM orchestration (§12).
    anthropic_model: str = Field(default="claude-sonnet-4-5")
    llm_max_questions: int = Field(default=4)  # §12 hard limit on clarifying questions
    llm_max_tool_turns: int = Field(default=12)  # safety cap on the agent loop
    # Whether unreviewed (draft) assemblies appear in the LLM index. §8 says they
    # should not in production; enable in dev/test to exercise the flow pre-review.
    llm_include_draft_assemblies: bool = Field(default=False)

    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_pass: str = Field(default="")
    smtp_from: str = Field(default="")

    sentry_dsn: str = Field(default="")

    # Data directories (assemblies + price book live in version control).
    data_dir: Path = Field(default=_REPO_ROOT / "data")

    # Where contractor logos are stored (Railway volume — see §23.6 decision).
    logo_storage_dir: Path = Field(default=_REPO_ROOT / "var" / "logos")

    @property
    def async_database_url(self) -> str:
        """DB URL with a guaranteed async driver (asyncpg / aiosqlite)."""
        return normalize_async_db_url(self.database_url)[0]

    @property
    def db_connect_args(self) -> dict:
        return normalize_async_db_url(self.database_url)[1]

    @property
    def assemblies_dir(self) -> Path:
        return self.data_dir / "assemblies"

    @property
    def pricebook_path(self) -> Path:
        return self.data_dir / "pricebook" / "materials.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
