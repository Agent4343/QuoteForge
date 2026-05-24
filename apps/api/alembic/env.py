"""Alembic async migration environment (§6, §18).

The database URL is taken from application settings. Online migrations run via
an async engine. On PostgreSQL a transactional advisory lock guards against
concurrent migrations across replicas (§18).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import quoteforge_api.models  # noqa: F401  (registers all tables on Base)
from alembic import context
from quoteforge_api.config import get_settings
from quoteforge_api.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Arbitrary but stable key for the migration advisory lock.
_MIGRATION_LOCK_KEY = 728_193_021


def _url() -> str:
    return get_settings().async_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:  # noqa: ANN001
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    # Bound the connect attempt (asyncpg) so an unreachable DB fails fast and
    # loudly instead of hanging startup past the healthcheck window.
    connect_args = dict(get_settings().db_connect_args)
    if _url().startswith("postgresql"):
        connect_args.setdefault("timeout", 15)
    engine = create_async_engine(_url(), connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
