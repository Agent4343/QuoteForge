"""Async database engine, session factory, and FastAPI dependency (§6).

SQLAlchemy 2.0 async. Production uses PostgreSQL via asyncpg; tests use
SQLite via aiosqlite. Models use portable column types (Uuid, Numeric, JSON,
non-native Enum) so the same metadata works on both.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from quoteforge_api.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    url = get_settings().database_url
    # SQLite needs check_same_thread off for the async driver in tests.
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a scoped async session."""
    sm = get_sessionmaker()
    async with sm() as session:
        yield session
