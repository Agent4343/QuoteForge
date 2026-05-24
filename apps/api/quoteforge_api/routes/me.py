"""Current-contractor profile and business settings (§13)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from quoteforge_api.auth.dependencies import CurrentUser, SessionDep
from quoteforge_api.schemas.user import UserOut, UserUpdate
from quoteforge_api.services import logos

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", response_model=UserOut)
async def update_me(body: UserUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/logo", response_model=UserOut)
async def upload_logo(
    user: CurrentUser, session: SessionDep, file: Annotated[UploadFile, File()]
) -> UserOut:
    data = await file.read()
    try:
        user.logo_url = logos.save_logo(user.id, file.content_type or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
