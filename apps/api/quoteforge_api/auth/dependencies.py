"""Auth dependencies: resolve the current contractor from a bearer token (§16)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from quoteforge_api.auth.security import decode_token
from quoteforge_api.db import get_session
from quoteforge_api.models import User

_bearer = HTTPBearer(auto_error=True)

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user_id = decode_token(creds.credentials, expected_type="access")
    if user_id is None:
        raise _UNAUTH
    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise _UNAUTH from exc
    user = await session.get(User, uid)
    if user is None:
        raise _UNAUTH
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
