"""Dashboard stats (§4, §13): open quotes, win rate, average margin."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, DecimalException

from fastapi import APIRouter
from sqlalchemy import func, select

from quoteforge_api.assemblies.loader import AssemblyLibrary, get_library
from quoteforge_api.auth.dependencies import CurrentUser, SessionDep
from quoteforge_api.models import LLMSession, Quote, QuoteLineItem
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

    # AI usage: aggregate LLM cost/tokens across this contractor's quotes (§19).
    llm = (
        await session.execute(
            select(
                func.coalesce(func.sum(LLMSession.cost_cad), 0),
                func.coalesce(func.sum(LLMSession.input_tokens), 0),
                func.coalesce(func.sum(LLMSession.output_tokens), 0),
                func.count(LLMSession.id),
            )
            .select_from(LLMSession)
            .join(Quote, LLMSession.quote_id == Quote.id)
            .where(Quote.user_id == user.id)
        )
    ).one()
    llm_cost, llm_in, llm_out, llm_sessions = llm

    return {
        "open_quotes": open_quotes,
        "approved": approved,
        "declined": declined,
        "win_rate_pct": float(win_rate) if win_rate is not None else None,
        "average_margin_pct": round(float(avg_margin), 2) if avg_margin is not None else None,
        "llm_cost_cad": round(float(llm_cost), 4),
        "llm_input_tokens": int(llm_in),
        "llm_output_tokens": int(llm_out),
        "ai_sessions": int(llm_sessions),
    }


def _normalize(value: object) -> str:
    """Canonical form for comparing a stored parameter value to a default.

    Numerics compare regardless of int/float/string encoding (the line-item
    editor stores numbers as strings); booleans and enum strings compare as
    lowercased text.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    try:
        return str(Decimal(str(value)).normalize())
    except (DecimalException, ValueError):
        return str(value).strip().lower()


def _is_edited(assembly_id: str, params: dict | None, lib: AssemblyLibrary) -> bool:
    """True if any declared parameter deviates from the assembly's default."""
    if not params or assembly_id not in lib:
        return False
    assembly = lib.get(assembly_id)
    for name, spec in assembly.parameters.items():
        if name in params and _normalize(params[name]) != _normalize(spec.default):
            return True
    return False


@dataclass
class _Agg:
    line_count: int = 0
    edited_count: int = 0
    total_quantity: Decimal = field(default_factory=lambda: Decimal(0))
    quote_ids: set = field(default_factory=set)


@router.get("/assemblies")
async def assembly_metrics(user: CurrentUser, session: SessionDep) -> dict:
    """Per-assembly usage and edit-rate metrics (§19).

    Across this contractor's quotes: how often each assembly is used, and how
    often a line's parameters deviate from the assembly's defaults. A high edit
    rate is a signal that an assembly's defaults are off and it should be
    prioritised for electrician review (§8/§22). Note: a deviation can also come
    from the AI choosing a job-specific value, so treat it as a review signal,
    not a literal count of manual keystrokes.
    """
    rows = (
        await session.execute(
            select(
                QuoteLineItem.assembly_id,
                QuoteLineItem.parameters,
                QuoteLineItem.quantity,
                QuoteLineItem.quote_id,
            )
            .join(Quote, QuoteLineItem.quote_id == Quote.id)
            .where(Quote.user_id == user.id, QuoteLineItem.assembly_id.is_not(None))
        )
    ).all()

    lib = get_library()
    aggs: dict[str, _Agg] = {}
    for assembly_id, params, quantity, quote_id in rows:
        agg = aggs.setdefault(assembly_id, _Agg())
        agg.line_count += 1
        agg.quote_ids.add(quote_id)
        agg.total_quantity += Decimal(str(quantity or 0))
        if _is_edited(assembly_id, params, lib):
            agg.edited_count += 1

    items = []
    for assembly_id, agg in aggs.items():
        assembly = lib.get(assembly_id) if assembly_id in lib else None
        items.append(
            {
                "assembly_id": assembly_id,
                "name_en": assembly.names.en if assembly else assembly_id,
                "name_fr": assembly.names.fr if assembly else assembly_id,
                "category": assembly.category.value if assembly else None,
                "status": assembly.status.value if assembly else "unknown",
                "line_count": agg.line_count,
                "quote_count": len(agg.quote_ids),
                "total_quantity": float(agg.total_quantity),
                "edited_count": agg.edited_count,
                "edit_rate_pct": round(agg.edited_count / agg.line_count * 100, 1),
            }
        )
    items.sort(key=lambda x: (x["line_count"], x["edit_rate_pct"]), reverse=True)
    return {"assemblies": items}
