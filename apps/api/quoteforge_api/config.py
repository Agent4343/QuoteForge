"""Application configuration (§18 environment variables).

Secrets and deployment knobs come from the environment. Data paths default to
the version-controlled ``/data`` directory at the repo root but can be
overridden (e.g. in a container image where data is copied elsewhere).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../apps/api/quoteforge_api/config.py -> repo root is three parents up.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    environment: str = Field(default="dev")  # dev | staging | prod
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="postgresql+asyncpg://localhost/quoteforge")
    jwt_secret: str = Field(default="dev-insecure-change-me")
    anthropic_api_key: str = Field(default="")

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
    def assemblies_dir(self) -> Path:
        return self.data_dir / "assemblies"

    @property
    def pricebook_path(self) -> Path:
        return self.data_dir / "pricebook" / "materials.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
