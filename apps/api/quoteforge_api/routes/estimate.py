"""Stateless estimate-preview route. Wraps the engine + audit (no persistence)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quoteforge_api.schemas.estimate import (
    EstimatePreviewRequest,
    EstimatePreviewResponse,
    LineItemOut,
    PreviewAuditFlagOut,
    TaxOut,
)
from quoteforge_api.services.audit import AuditContext, run_audit
from quoteforge_api.services.estimating import (
    AssemblyRequest,
    ContractorRates,
    CustomLineItem,
    compute_estimate,
)

router = APIRouter(prefix="/api/estimate", tags=["estimate"])


@router.post("/preview", response_model=EstimatePreviewResponse)
def preview(req: EstimatePreviewRequest) -> EstimatePreviewResponse:
    rates = ContractorRates(
        blended_labor_rate_cad=req.contractor.blended_labor_rate_cad,
        apprentice_labor_rate_cad=req.contractor.apprentice_labor_rate_cad,
        default_material_markup_pct=req.contractor.default_material_markup_pct,
        default_labor_markup_pct=req.contractor.default_labor_markup_pct,
        minimum_callout_hours=req.contractor.minimum_callout_hours,
    )
    assemblies = [
        AssemblyRequest(a.assembly_id, a.quantity, a.parameters) for a in req.assemblies
    ]
    extras = [
        CustomLineItem(c.description_en, c.description_fr, c.amount_cad, c.source, c.labor_hours)
        for c in req.additional_line_items
    ]

    try:
        result = compute_estimate(
            rates,
            req.province,
            req.code_edition,
            assemblies,
            extras,
            permit_date=req.permit_date,
            material_markup_pct=req.material_markup_pct,
            labor_markup_pct=req.labor_markup_pct,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from quoteforge_api.assemblies.loader import get_library
    from quoteforge_api.pricebook import get_pricebook

    audit = run_audit(
        AuditContext(
            estimate=result,
            contractor_minimum_margin_pct=req.contractor.minimum_margin_pct,
            province=req.province,
            requested_assemblies=assemblies,
            library=get_library(),
            pricebook=get_pricebook(),
            job_description=req.job_description,
            customer_facing_scope=req.customer_facing_scope,
            customer_province=req.customer_province,
            customer_language=req.customer_language,
            permit_date=req.permit_date,
        )
    )

    return EstimatePreviewResponse(
        line_items=[
            LineItemOut(
                line_number=li.line_number,
                source=li.source,
                assembly_id=li.assembly_id,
                description_en=li.description_en,
                description_fr=li.description_fr,
                quantity=li.quantity,
                materials_cost_cad=li.materials_cost_cad,
                labor_hours=li.labor_hours,
                labor_cost_cad=li.labor_cost_cad,
                line_total_cad=li.line_total_cad,
                code_refs=li.code_refs,
            )
            for li in result.line_items
        ],
        subtotal_materials_cad=result.subtotal_materials_cad,
        subtotal_labor_cad=result.subtotal_labor_cad,
        subtotal_permits_cad=result.subtotal_permits_cad,
        subtotal_other_cad=result.subtotal_other_cad,
        tax=TaxOut(
            gst_cad=result.tax.gst_cad,
            gst_rate=result.tax.gst_rate,
            pst_qst_hst_cad=result.tax.pst_qst_hst_cad,
            pst_qst_hst_rate=result.tax.pst_qst_hst_rate,
            pst_qst_hst_label_en=result.tax.pst_qst_hst_label_en,
            total_tax_cad=result.tax.total_tax_cad,
        ),
        total_cad=result.total_cad,
        gross_margin_pct=result.gross_margin_pct,
        code_edition=result.code_edition,
        assumptions=result.assumptions,
        audit_flags=[
            PreviewAuditFlagOut(
                severity=f.severity,
                code=f.code,
                message_en=f.message_en,
                message_fr=f.message_fr,
                suggested_action_en=f.suggested_action_en,
                suggested_action_fr=f.suggested_action_fr,
            )
            for f in audit.flags
        ],
        audit_passed=audit.passed,
        pdf_blocked=audit.blocks_pdf,
    )
