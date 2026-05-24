"""DB URL normalization for managed hosts (Railway/Heroku) — §18."""

from quoteforge_api.config import Settings, normalize_async_db_url


def test_is_deployed_is_case_insensitive():
    assert Settings(environment="Prod").is_deployed is True
    assert Settings(environment="PRODUCTION").is_deployed is True
    assert Settings(environment="staging").is_deployed is True
    assert Settings(environment="dev").is_deployed is False
    assert Settings(environment="test").is_deployed is False


def test_postgres_scheme_rewritten_to_asyncpg():
    url, args = normalize_async_db_url("postgres://u:p@host:5432/db")
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert args == {}


def test_postgresql_scheme_rewritten_to_asyncpg():
    url, _ = normalize_async_db_url("postgresql://u:p@host:5432/db")
    assert url == "postgresql+asyncpg://u:p@host:5432/db"


def test_sslmode_moved_to_connect_args():
    url, args = normalize_async_db_url("postgresql://u:p@host/db?sslmode=require")
    assert "sslmode" not in url
    assert url.startswith("postgresql+asyncpg://")
    assert args == {"ssl": True}


def test_channel_binding_stripped():
    url, args = normalize_async_db_url(
        "postgresql://u:p@host/db?sslmode=require&channel_binding=require"
    )
    assert "channel_binding" not in url
    assert args == {"ssl": True}


def test_already_async_url_unchanged():
    url, args = normalize_async_db_url("postgresql+asyncpg://u:p@host/db")
    assert url == "postgresql+asyncpg://u:p@host/db"
    assert args == {}


def test_sqlite_unchanged():
    url, args = normalize_async_db_url("sqlite+aiosqlite:///./x.db")
    assert url == "sqlite+aiosqlite:///./x.db"
    assert args == {}


def test_trailing_whitespace_is_stripped():
    # A stray newline/tab pasted into the env var must not end up in the dbname.
    url, _ = normalize_async_db_url("postgresql://u:p@host:5432/postgres\n\t\t")
    assert url == "postgresql+asyncpg://u:p@host:5432/postgres"
    assert not url.endswith(("\n", "\t", " "))
