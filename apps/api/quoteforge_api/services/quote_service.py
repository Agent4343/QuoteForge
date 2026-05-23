"""Quote orchestration: numbering, recompute (engine), and audit persistence.

The engine and audit are pure; this module is the thin bridge that reads a
persisted quote, runs them, and writes results back. Computed numbers are
written here only via the engine — never by the LLM (principle §3.1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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

# Default code edition per province, locked onto a quote at creation (§3.3/§3.4).
_DEFAULT_CODE_EDITION: dict[Province, str] = {
    Province.ON: "OESC 2024 (28th)",
    Province.QC: "Chapitre V (CCÉ 2015 + modifications QC)",
}


def default_code_edition(province: Province) -> str:
    return _DEFAULT_CODE_EDITION.get(province, "")


def default_customer_language(province: Province) -> Language:
    return Language.FR if province == Province.QC else Language.EN


def contractor_rates(user: User) -> ContractorRates:
    return ContractorRates(
        blended_labor_rate_cad=user.blended_labor_rate_cad,
        apprentice_labor_rate_cad=user.apprentice_labor_rate_cad,
        default_material_markup_pct=user.default_material_markup_pct,
        default_labor_markup_pct=user.default_labor_markup_pct,
        minimum_callout_hours=user.minimum_callout_hours,
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
            assemblies.append(AssemblyRequest(li.assembly_id, li.quantity, params))
        else:
            extras.append(
                CustomLineItem(
                    description_en=li.description_en,
                    description_fr=li.description_fr,
                    amount_cad=li.line_total_cad,
                    source=li.source.value,
                    labor_hours=li.labor_hours,
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
