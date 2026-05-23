"""Dashboard stats (§4, §13): open quotes, win rate, average margin."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from quoteforge_api.auth.dependencies import CurrentUser, SessionDep
from quoteforge_api.models import Quote
from quoteforge_api.models.enums import QuoteStatus

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def stats(user: CurrentUser, session: SessionDep) -> dict:
    base = select(func.count()).select_from(Quote).where(Quote.user_id == user.id)

    async def count(*conds) -> int:
        return (await session.scalar(base.where(*conds))) or 0

    open_quotes = await count(Quote.status.in_([QuoteStatus.DRAFT, QuoteStatus.SENT]))
    approved = await count(Quote.status == QuoteStatus.APPROVED)
    declined = await count(Quote.status == QuoteStatus.DECLINED)
    decided = approved + declined
    win_rate = (Decimal(approved) / Decimal(decided) * 100).quantize(Decimal("0.1")) if decided else None

    avg_margin = await session.scalar(
        select(func.avg(Quote.gross_margin_pct)).where(
            Quote.user_id == user.id, Quote.status != QuoteStatus.DRAFT
        )
    )

    return {
        "open_quotes": open_quotes,
        "approved": approved,
        "declined": declined,
        "win_rate_pct": float(win_rate) if win_rate is not None else None,
        "average_margin_pct": round(float(avg_margin), 2) if avg_margin is not None else None,
    }
