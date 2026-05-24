"""Authentication routes (§13, §16)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from quoteforge_api.auth.dependencies import SessionDep
from quoteforge_api.auth.ratelimit import rate_limit
from quoteforge_api.auth.security import (
    create_access_token,
    create_reset_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from quoteforge_api.models import RefreshToken, User
from quoteforge_api.models.enums import Language
from quoteforge_api.provinces import Province
from quoteforge_api.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from quoteforge_api.services.email import send_password_reset

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("quoteforge.auth")

_AuthLimit = Depends(rate_limit("auth", limit=10, window_seconds=60))


async def _issue_tokens(session: SessionDep, user: User) -> TokenResponse:
    raw, token_hash, expires_at = generate_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await session.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)), refresh_token=raw)


@router.post("/register", response_model=TokenResponse, status_code=201, dependencies=[_AuthLimit])
async def register(body: RegisterRequest, session: SessionDep) -> TokenResponse:
    logger.info("register attempt: email=%s province=%s", body.email, body.province)
    exists = await session.scalar(select(User).where(User.email == body.email.lower()))
    if exists:
        logger.info("register rejected: email already exists (%s)", body.email)
        raise HTTPException(status_code=409, detail="Email already registered")
    # Quebec contractors default to French customer-facing output (§3).
    language = body.language or (Language.FR if body.province == Province.QC else Language.EN)
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        business_name=body.business_name,
        province=body.province,
        language=language,
    )
    session.add(user)
    await session.flush()
    tokens = await _issue_tokens(session, user)
    logger.info("register success: email=%s id=%s", user.email, user.id)
    return tokens


@router.post("/login", response_model=TokenResponse, dependencies=[_AuthLimit])
async def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    logger.info("login attempt: email=%s", body.email)
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return await _issue_tokens(session, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenResponse:
    token_hash = hash_refresh_token(body.refresh_token)
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(UTC)
    expires_at = row.expires_at if row else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if row is None or row.revoked or expires_at < now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # Rotate: revoke the presented token and issue a new pair.
    row.revoked = True
    user = await session.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return await _issue_tokens(session, user)


@router.post("/password-reset/request", status_code=202, dependencies=[_AuthLimit])
async def password_reset_request(body: PasswordResetRequest, session: SessionDep) -> dict:
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    # Always return 202 to avoid leaking which emails are registered.
    if user is not None:
        send_password_reset(user.email, create_reset_token(str(user.id)))
    return {"status": "accepted"}


@router.post("/password-reset/confirm", dependencies=[_AuthLimit])
async def password_reset_confirm(
    body: PasswordResetConfirm, session: SessionDep
) -> dict:
    user_id = decode_token(body.token, expected_type="reset")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = await session.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    user.password_hash = hash_password(body.new_password)
    # Revoke all refresh tokens on password change.
    for row in await session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)):
        row.revoked = True
    await session.commit()
    return {"status": "ok"}
