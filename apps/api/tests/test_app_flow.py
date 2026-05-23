"""End-to-end API flow tests: auth, isolation, and the quote lifecycle.

Each test gets an isolated SQLite database and a fresh ASGI client. The
estimating engine and audit run for real against the version-controlled
assemblies/price book.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import quoteforge_api.models  # noqa: F401  (register tables)
from quoteforge_api.auth import ratelimit
from quoteforge_api.auth.security import create_reset_token
from quoteforge_api.db import Base, get_session
from quoteforge_api.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    ratelimit.reset()
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator:
        async with sm() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()
    os.unlink(path)


async def _register(client, email="contractor@example.com", province="ON") -> str:
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "supersecret123", "full_name": "Sam Sparks",
        "business_name": "Sparks Electric", "province": province,
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _set_rates(client, token):
    r = await client.patch("/api/me", headers=_auth(token), json={
        "blended_labor_rate_cad": "110", "default_material_markup_pct": "35",
        "default_labor_markup_pct": "0", "minimum_callout_hours": "1", "minimum_margin_pct": "20",
    })
    assert r.status_code == 200, r.text


async def _create_customer(client, token, province="ON") -> str:
    r = await client.post("/api/customers", headers=_auth(token), json={
        "name": "Jane Homeowner", "address_line1": "1 Main St", "city": "Ottawa",
        "province": province, "postal_code": "K1A0A1",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_register_login_me(client):
    token = await _register(client)
    me = await client.get("/api/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["business_name"] == "Sparks Electric"

    login = await client.post("/api/auth/login", json={
        "email": "contractor@example.com", "password": "supersecret123"})
    assert login.status_code == 200
    bad = await client.post("/api/auth/login", json={
        "email": "contractor@example.com", "password": "wrong"})
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_quebec_register_defaults_to_french(client):
    token = await _register(client, email="qc@example.com", province="QC")
    me = await client.get("/api/me", headers=_auth(token))
    assert me.json()["language"] == "fr"


@pytest.mark.asyncio
async def test_quote_lifecycle_with_engine_and_audit(client):
    token = await _register(client)
    await _set_rates(client, token)
    customer_id = await _create_customer(client, token)

    create = await client.post("/api/quotes", headers=_auth(token), json={
        "customer_id": customer_id,
        "job_title": "New kitchen circuit",
        "line_items": [{
            "source": "assembly", "assembly_id": "circuit_new_15a_residential",
            "quantity": "1", "parameters": {"run_length_ft": 40, "access": "open"},
        }],
    })
    assert create.status_code == 201, create.text
    q = create.json()
    assert q["quote_number"] == "Q-2026-0001"
    assert q["code_edition"] == "OESC 2024 (28th)"
    assert Decimal(q["total_cad"]) == Decimal("242.02")
    # Underbid (35% material markup, 0 labour markup) -> below 20% min -> blocked.
    assert q["pdf_blocked"] is True
    assert any(f["code"] == "MARGIN_BELOW_MIN" for f in q["audit_flags"])

    # Sending is blocked while a critical flag is outstanding.
    blocked_send = await client.post(f"/api/quotes/{q['id']}/send", headers=_auth(token))
    assert blocked_send.status_code == 409

    # Override the critical margin flag, then send.
    crit = next(f for f in q["audit_flags"] if f["code"] == "MARGIN_BELOW_MIN")
    ov = await client.post(f"/api/quotes/{q['id']}/override-flag", headers=_auth(token),
                           json={"flag_id": crit["id"]})
    assert ov.status_code == 200
    assert ov.json()["pdf_blocked"] is False

    sent = await client.post(f"/api/quotes/{q['id']}/send", headers=_auth(token))
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_customer_and_quote_isolation_between_users(client):
    token_a = await _register(client, email="a@example.com")
    token_b = await _register(client, email="b@example.com")
    cust_a = await _create_customer(client, token_a)

    # B cannot read A's customer.
    r = await client.get(f"/api/customers/{cust_a}", headers=_auth(token_b))
    assert r.status_code == 404

    await _set_rates(client, token_a)
    quote = await client.post("/api/quotes", headers=_auth(token_a), json={
        "customer_id": cust_a, "job_title": "x",
        "line_items": [{"source": "assembly", "assembly_id": "recep_duplex_15a_residential"}],
    })
    qid = quote.json()["id"]
    # B cannot read A's quote.
    assert (await client.get(f"/api/quotes/{qid}", headers=_auth(token_b))).status_code == 404
    # B's quote list is empty.
    assert (await client.get("/api/quotes", headers=_auth(token_b))).json() == []


@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    r = await client.post("/api/auth/register", json={
        "email": "rot@example.com", "password": "supersecret123", "full_name": "R",
        "business_name": "RB", "province": "ON"})
    refresh = r.json()["refresh_token"]
    first = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200
    # Old refresh token is now revoked.
    reuse = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_confirm(client):
    token = await _register(client, email="reset@example.com")
    me = await client.get("/api/me", headers=_auth(token))
    user_id = me.json()["id"]
    reset_token = create_reset_token(user_id)
    confirm = await client.post("/api/auth/password-reset/confirm", json={
        "token": reset_token, "new_password": "brandnewpass456"})
    assert confirm.status_code == 200
    # New password works; old one does not.
    assert (await client.post("/api/auth/login", json={
        "email": "reset@example.com", "password": "brandnewpass456"})).status_code == 200
    assert (await client.post("/api/auth/login", json={
        "email": "reset@example.com", "password": "supersecret123"})).status_code == 401


@pytest.mark.asyncio
async def test_dashboard_stats(client):
    token = await _register(client)
    await _set_rates(client, token)
    cust = await _create_customer(client, token)
    await client.post("/api/quotes", headers=_auth(token), json={
        "customer_id": cust, "job_title": "x",
        "line_items": [{"source": "assembly", "assembly_id": "recep_duplex_15a_residential"}]})
    stats = await client.get("/api/dashboard/stats", headers=_auth(token))
    assert stats.status_code == 200
    assert stats.json()["open_quotes"] == 1


@pytest.mark.asyncio
async def test_generate_and_pdf_not_implemented(client):
    token = await _register(client)
    cust = await _create_customer(client, token)
    q = await client.post("/api/quotes", headers=_auth(token), json={
        "customer_id": cust, "job_title": "x"})
    qid = q.json()["id"]
    assert (await client.post(f"/api/quotes/{qid}/generate", headers=_auth(token))).status_code == 501
    assert (await client.get(f"/api/quotes/{qid}/pdf", headers=_auth(token))).status_code == 501
