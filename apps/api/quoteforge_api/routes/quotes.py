"""Quote CRUD + lifecycle (§13). LLM generation and PDF are separate, later phases."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from quoteforge_api.auth import ratelimit
from quoteforge_api.auth.dependencies import CurrentUser, SessionDep
from quoteforge_api.config import get_settings
from quoteforge_api.models import Customer, LLMSession, Quote, QuoteLineItem
from quoteforge_api.models.enums import LineSource, QuoteStatus
from quoteforge_api.schemas.llm import AnswerQuestionRequest, GenerateRequest, GenerationResponse
from quoteforge_api.schemas.quote import (
    MarkStatusRequest,
    OverrideFlagRequest,
    QuoteCreate,
    QuoteLineItemIn,
    QuoteOut,
    QuoteSummary,
    QuoteUpdate,
)
from quoteforge_api.services import quote_service
from quoteforge_api.services.llm import client as llm_client
from quoteforge_api.services.llm import estimator
from quoteforge_api.services.llm.tools import ToolContext

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

_VALIDITY_DAYS = 30


async def _load_quote(session: SessionDep, user: CurrentUser, quote_id: uuid.UUID) -> Quote:
    quote = await session.scalar(
        select(Quote)
        .where(Quote.id == quote_id, Quote.user_id == user.id)
        .options(selectinload(Quote.line_items), selectinload(Quote.audit_flags))
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


def _serialize(quote: Quote) -> QuoteOut:
    out = QuoteOut.model_validate(quote)
    out.pdf_blocked = quote_service.pdf_blocked(quote)
    return out


def _input_rows(items: list[QuoteLineItemIn]) -> list[QuoteLineItem]:
    rows: list[QuoteLineItem] = []
    for i, item in enumerate(items, start=1):
        if item.source == LineSource.ASSEMBLY:
            rows.append(QuoteLineItem(
                line_number=i, source=LineSource.ASSEMBLY, assembly_id=item.assembly_id,
                description_en="", description_fr="", quantity=item.quantity,
                parameters=item.parameters, is_optional=item.is_optional,
            ))
        else:
            rows.append(QuoteLineItem(
                line_number=i, source=item.source, assembly_id=None,
                description_en=item.description_en or "", description_fr=item.description_fr or "",
                quantity=item.quantity, parameters={},
                line_total_cad=item.amount_cad or 0, labor_hours=item.labor_hours,
                is_optional=item.is_optional,
            ))
    return rows


@router.get("", response_model=list[QuoteSummary])
async def list_quotes(
    user: CurrentUser,
    session: SessionDep,
    status: Annotated[QuoteStatus | None, Query()] = None,
) -> list[Quote]:
    stmt = select(Quote).where(Quote.user_id == user.id)
    if status is not None:
        stmt = stmt.where(Quote.status == status)
    rows = await session.scalars(stmt.order_by(Quote.created_at.desc()))
    return list(rows)


@router.post("", response_model=QuoteOut, status_code=201)
async def create_quote(body: QuoteCreate, user: CurrentUser, session: SessionDep) -> QuoteOut:
    customer = await session.scalar(
        select(Customer).where(Customer.id == body.customer_id, Customer.user_id == user.id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    province = body.province or customer.province
    today = date.today()
    quote = Quote(
        user_id=user.id,
        customer_id=customer.id,
        quote_number=await quote_service.next_quote_number(session, user.id, today.year),
        job_title=body.job_title,
        job_description=body.job_description,
        job_site_address=body.job_site_address,
        province=province,
        code_edition=body.code_edition
        or quote_service.default_code_edition(province, body.permit_expected_date),
        permit_expected_date=body.permit_expected_date,
        customer_language=body.customer_language
        or quote_service.default_customer_language(province),
        valid_until=body.valid_until or (today + timedelta(days=_VALIDITY_DAYS)),
        line_items=_input_rows(body.line_items),
    )
    session.add(quote)
    await session.flush()
    # Load both child collections so the engine recompute can reassign them
    # without triggering a sync lazy-load inside the (async) request.
    await session.refresh(quote, attribute_names=["line_items", "audit_flags"])
    quote_service.recompute_quote(quote, user, customer)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.get("/{quote_id}", response_model=QuoteOut)
async def get_quote(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> QuoteOut:
    return _serialize(await _load_quote(session, user, quote_id))


@router.patch("/{quote_id}", response_model=QuoteOut)
async def update_quote(
    quote_id: uuid.UUID, body: QuoteUpdate, user: CurrentUser, session: SessionDep
) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft quotes can be edited")
    data = body.model_dump(exclude_unset=True)
    new_items = data.pop("line_items", None)
    for field, value in data.items():
        setattr(quote, field, value)
    if new_items is not None:
        quote.line_items = _input_rows([QuoteLineItemIn(**i) for i in new_items])
    customer = await session.get(Customer, quote.customer_id)
    quote_service.recompute_quote(quote, user, customer)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.delete("/{quote_id}", status_code=204)
async def delete_quote(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    quote = await _load_quote(session, user, quote_id)
    await session.delete(quote)
    await session.commit()


@router.post("/{quote_id}/recompute", response_model=QuoteOut)
async def recompute(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    customer = await session.get(Customer, quote.customer_id)
    quote_service.recompute_quote(quote, user, customer)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.post("/{quote_id}/audit", response_model=QuoteOut)
async def audit(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> QuoteOut:
    # Deterministic: re-runs the engine + audit over the current input lines.
    return await recompute(quote_id, user, session)


@router.post("/{quote_id}/override-flag", response_model=QuoteOut)
async def override_flag(
    quote_id: uuid.UUID, body: OverrideFlagRequest, user: CurrentUser, session: SessionDep
) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    flag = next((f for f in quote.audit_flags if f.id == body.flag_id), None)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag.overridden = True
    flag.overridden_at = datetime.now(UTC)
    quote.audit_passed = not quote_service.pdf_blocked(quote)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.post("/{quote_id}/finalize", response_model=QuoteOut)
async def finalize(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    if quote_service.pdf_blocked(quote):
        raise HTTPException(
            status_code=409,
            detail="Critical audit flags must be overridden before finalizing.",
        )
    # §24.2: lint the customer scope's terminology before the PDF is produced.
    quote_service.ensure_terminology_flag(quote)
    quote.audit_passed = True
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.post("/{quote_id}/send", response_model=QuoteOut)
async def send(quote_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    if quote_service.pdf_blocked(quote):
        raise HTTPException(status_code=409, detail="Resolve critical audit flags before sending.")
    quote.status = QuoteStatus.SENT
    quote_service.mark_sent(quote)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


@router.post("/{quote_id}/mark-status", response_model=QuoteOut)
async def mark_status(
    quote_id: uuid.UUID, body: MarkStatusRequest, user: CurrentUser, session: SessionDep
) -> QuoteOut:
    quote = await _load_quote(session, user, quote_id)
    quote.status = body.status
    if body.status == QuoteStatus.APPROVED:
        quote.approved_at = datetime.now(UTC)
    await session.commit()
    return _serialize(await _load_quote(session, user, quote.id))


def _build_tool_context(quote: Quote, user, customer) -> ToolContext:
    from quoteforge_api.assemblies.loader import get_library
    from quoteforge_api.pricebook import get_pricebook

    return ToolContext(
        quote=quote,
        user=user,
        customer=customer,
        library=get_library(),
        pricebook=get_pricebook(),
        include_draft=get_settings().llm_include_draft_assemblies,
    )


async def _get_or_create_llm_session(session: SessionDep, quote_id: uuid.UUID) -> LLMSession:
    llm_session = await session.scalar(select(LLMSession).where(LLMSession.quote_id == quote_id))
    if llm_session is None:
        llm_session = LLMSession(quote_id=quote_id, messages=[], tool_calls=[])
        session.add(llm_session)
        await session.flush()
    return llm_session


@router.post("/{quote_id}/generate", response_model=GenerationResponse)
async def generate(
    quote_id: uuid.UUID, body: GenerateRequest, user: CurrentUser, session: SessionDep
) -> GenerationResponse:
    ratelimit.enforce(
        f"generate:{user.id}", limit=get_settings().llm_generates_per_hour, window_seconds=3600
    )  # §16
    quote = await _load_quote(session, user, quote_id)
    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft quotes can be generated")
    job = body.job_description or quote.job_description
    if not job:
        raise HTTPException(status_code=422, detail="A job description is required")
    if body.job_description:
        quote.job_description = body.job_description

    customer = await session.get(Customer, quote.customer_id)
    llm_session = await _get_or_create_llm_session(session, quote.id)
    ctx = _build_tool_context(quote, user, customer)
    try:
        client = llm_client.get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = estimator.start_generation(ctx, client, llm_session, job)
    await session.commit()
    quote = await _load_quote(session, user, quote_id)
    return GenerationResponse(
        status=result.status, question=result.question,
        assistant_text=result.assistant_text, error=result.error, quote=_serialize(quote),
    )


@router.post("/{quote_id}/answer-question", response_model=GenerationResponse)
async def answer_question(
    quote_id: uuid.UUID, body: AnswerQuestionRequest, user: CurrentUser, session: SessionDep
) -> GenerationResponse:
    quote = await _load_quote(session, user, quote_id)
    customer = await session.get(Customer, quote.customer_id)
    llm_session = await session.scalar(
        select(LLMSession).where(LLMSession.quote_id == quote.id)
    )
    if llm_session is None:
        raise HTTPException(status_code=409, detail="No active generation to answer")
    ctx = _build_tool_context(quote, user, customer)
    try:
        client = llm_client.get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = estimator.continue_generation(ctx, client, llm_session, body.answer)
    await session.commit()
    quote = await _load_quote(session, user, quote_id)
    return GenerationResponse(
        status=result.status, question=result.question,
        assistant_text=result.assistant_text, error=result.error, quote=_serialize(quote),
    )


@router.get("/{quote_id}/pdf")
async def pdf(
    quote_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    variant: Annotated[str, Query(pattern="^(customer|internal)$")] = "customer",
) -> Response:
    from quoteforge_api.services.pdf import renderer

    quote = await _load_quote(session, user, quote_id)
    customer = await session.get(Customer, quote.customer_id)
    if variant == "internal":
        content = await asyncio.to_thread(renderer.render_internal_pdf, quote, user, customer)
        filename = f"{quote.quote_number}-internal.pdf"
    else:
        # Customer PDF is gated on the audit: no PDF while a critical flag is open (§3.5).
        if quote_service.pdf_blocked(quote):
            raise HTTPException(
                status_code=409,
                detail="Critical audit flags must be overridden before the customer PDF.",
            )
        content = await asyncio.to_thread(renderer.render_customer_pdf, quote, user, customer)
        filename = f"{quote.quote_number}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
