"""Quote orchestration: numbering, recompute (engine), and audit persistence.

The engine and audit are pure; this module is the thin bridge that reads a
persisted quote, runs them, and writes results back. Computed numbers are
written here only via the engine — never by the LLM (principle §3.1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from quoteforge_api.models import (
    Customer,
    EstimateAuditFlag,
    Quote,
    QuoteLineItem,
    User,
)
from quoteforge_api.models.enums import FlagSeverity, Language, LineSource
from quoteforge_api.pricebook import get_pricebook
from quoteforge_api.provinces import Province
from quoteforge_api.services.audit import AuditContext, run_audit
from quoteforge_api.services.estimating import (
    AssemblyRequest,
    ContractorRates,
    CustomLineItem,
    compute_estimate,
)
from quoteforge_api.services.estimating.engine import get_library

_GENERATED_MARKER = "_generated"


def default_code_edition(province: Province, permit_date: date | None = None) -> str:
    """Code edition in force for the province on the permit date (§3.3/§3.4).

    Sourced from the version-controlled code matrix (data/code_editions.yaml).
    """
    from quoteforge_api.code_editions import get_code_matrix

    return get_code_matrix().edition_in_force(province, permit_date)


def default_customer_language(province: Province) -> Language:
    from quoteforge_api.code_editions import get_code_matrix

    return Language(get_code_matrix().customer_language(province))


def contractor_rates(user: User) -> ContractorRates:
    return ContractorRates(
        blended_labor_rate_cad=user.blended_labor_rate_cad,
        apprentice_labor_rate_cad=user.apprentice_labor_rate_cad,
        default_material_markup_pct=user.default_material_markup_pct,
        default_labor_markup_pct=user.default_labor_markup_pct,
        minimum_callout_hours=user.minimum_callout_hours,
        labor_cost_rate_cad=user.labor_cost_rate_cad,
    )


async def next_quote_number(session: AsyncSession, user_id: uuid.UUID, year: int) -> str:
    prefix = f"Q-{year}-"
    count = await session.scalar(
        select(func.count())
        .select_from(Quote)
        .where(Quote.user_id == user_id, Quote.quote_number.like(f"{prefix}%"))
    )
    return f"{prefix}{(count or 0) + 1:04d}"


def pdf_blocked(quote: Quote) -> bool:
    """A quote is blocked while any critical flag remains un-overridden (§3.5)."""
    return any(
        f.severity == FlagSeverity.CRITICAL and not f.overridden for f in quote.audit_flags
    )


def _inputs_from_quote(quote: Quote) -> tuple[list[AssemblyRequest], list[CustomLineItem]]:
    assemblies: list[AssemblyRequest] = []
    extras: list[CustomLineItem] = []
    for li in quote.line_items:
        if isinstance(li.parameters, dict) and li.parameters.get(_GENERATED_MARKER):
            continue  # engine-synthesised line; not an input
        if li.source == LineSource.ASSEMBLY and li.assembly_id:
            params = {k: v for k, v in (li.parameters or {}).items() if k != _GENERATED_MARKER}
            assemblies.append(
                AssemblyRequest(li.assembly_id, li.quantity, params, is_optional=li.is_optional)
            )
        else:
            extras.append(
                CustomLineItem(
                    description_en=li.description_en,
                    description_fr=li.description_fr,
                    amount_cad=li.line_total_cad,
                    source=li.source.value,
                    labor_hours=li.labor_hours,
                    is_optional=li.is_optional,
                )
            )
    return assemblies, extras


def recompute_quote(quote: Quote, user: User, customer: Customer) -> None:
    """Run the engine + audit over a quote's input lines and write results back.

    Recompute resets prior flag overrides: changing the numbers invalidates an
    earlier decision to proceed, so the contractor must re-confirm (§3.5).
    """
    assemblies, extras = _inputs_from_quote(quote)
    apply_estimate(quote, user, customer, assemblies, extras)


def apply_estimate(
    quote: Quote,
    user: User,
    customer: Customer,
    assemblies: list[AssemblyRequest],
    extras: list[CustomLineItem],
) -> None:
    """Run the engine + audit for explicit inputs and persist onto the quote.

    Used both by recompute (inputs read from the quote) and by the LLM
    ``compute_estimate`` tool (inputs chosen by Claude). Numbers are produced
    only here, by the engine — never by the LLM (principle §3.1).
    """
    library = get_library()
    pricebook = get_pricebook()

    result = compute_estimate(
        contractor_rates(user),
        quote.province,
        quote.code_edition or "",
        assemblies,
        extras,
        permit_date=quote.permit_expected_date,
        library=library,
        pricebook=pricebook,
    )

    quote.line_items = [
        QuoteLineItem(
            line_number=li.line_number,
            source=LineSource(li.source),
            assembly_id=li.assembly_id,
            description_en=li.description_en,
            description_fr=li.description_fr,
            quantity=li.quantity,
            parameters=(
                {_GENERATED_MARKER: "minimum_callout"} if li.generated else dict(li.parameters)
            ),
            materials_cost_cad=li.materials_cost_cad,
            labor_hours=li.labor_hours,
            labor_cost_cad=li.labor_cost_cad,
            line_total_cad=li.line_total_cad,
            code_refs=li.code_refs,
            is_optional=li.is_optional,
        )
        for li in result.line_items
    ]

    quote.subtotal_materials_cad = result.subtotal_materials_cad
    quote.subtotal_labor_cad = result.subtotal_labor_cad
    quote.subtotal_permits_cad = result.subtotal_permits_cad
    quote.subtotal_other_cad = result.subtotal_other_cad
    quote.tax_gst_cad = result.tax.gst_cad
    quote.tax_pst_qst_hst_cad = result.tax.pst_qst_hst_cad
    quote.total_cad = result.total_cad
    quote.gross_margin_pct = result.gross_margin_pct

    audit = run_audit(
        AuditContext(
            estimate=result,
            contractor_minimum_margin_pct=user.minimum_margin_pct,
            province=quote.province,
            requested_assemblies=assemblies,
            library=library,
            pricebook=pricebook,
            job_description=quote.job_description or "",
            customer_facing_scope=(quote.customer_facing_scope_en or "")
            + " "
            + (quote.customer_facing_scope_fr or ""),
            customer_province=customer.province,
            customer_language=quote.customer_language.value,
            permit_date=quote.permit_expected_date,
        )
    )

    quote.audit_flags = [
        EstimateAuditFlag(
            severity=FlagSeverity(f.severity),
            code=f.code,
            message_en=f.message_en,
            message_fr=f.message_fr,
            suggested_action=f.suggested_action_en,
            overridden=False,
        )
        for f in audit.flags
    ]
    quote.audit_passed = not pdf_blocked(quote)


def mark_sent(quote: Quote) -> None:
    quote.sent_at = datetime.now(UTC)


def ensure_terminology_flag(quote: Quote) -> None:
    """Finalize-time terminology lint (§24.2).

    The LLM writes the customer scope after the last audit ran, so a terminology
    slip can reach finalize unflagged. This re-lints the persisted scope against
    the quote's assemblies and appends a (non-blocking) warn flag if one isn't
    already recorded — without disturbing existing flags or their overrides.
    """
    from quoteforge_api.assemblies.schema import Category
    from quoteforge_api.services.audit.rules import service_terminology_flag

    library = get_library()
    has_service_work = any(
        li.source == LineSource.ASSEMBLY
        and li.assembly_id
        and not li.is_optional
        and li.assembly_id in library
        and library.get(li.assembly_id).category == Category.SERVICE
        for li in quote.line_items
    )
    scope = (quote.customer_facing_scope_en or "") + " " + (quote.customer_facing_scope_fr or "")
    flag = service_terminology_flag(scope, has_service_work)
    if flag is None or any(f.code == flag.code for f in quote.audit_flags):
        return
    quote.audit_flags.append(
        EstimateAuditFlag(
            severity=FlagSeverity(flag.severity),
            code=flag.code,
            message_en=flag.message_en,
            message_fr=flag.message_fr,
            suggested_action=flag.suggested_action_en,
            overridden=False,
        )
    )
