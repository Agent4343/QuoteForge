"""Pydantic schemas for the stateless estimate-preview endpoint.

This exposes the deterministic engine + audit over HTTP without persistence, so
the core can be exercised before the full quote/auth stack (§13) is built.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from quoteforge_api.provinces import Province


class ContractorRatesIn(BaseModel):
    blended_labor_rate_cad: Decimal = Field(gt=0)
    apprentice_labor_rate_cad: Decimal = Field(default=Decimal("0"), ge=0)
    default_material_markup_pct: Decimal = Field(default=Decimal("35"), ge=0)
    default_labor_markup_pct: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_callout_hours: Decimal = Field(default=Decimal("1"), ge=0)
    minimum_margin_pct: Decimal = Field(default=Decimal("20"), ge=0)


class AssemblyRequestIn(BaseModel):
    assembly_id: str
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    parameters: dict[str, object] = Field(default_factory=dict)


class CustomLineItemIn(BaseModel):
    description_en: str
    description_fr: str
    amount_cad: Decimal = Field(ge=0)
    source: str = "custom"  # custom | permit
    labor_hours: Decimal = Field(default=Decimal("0"), ge=0)


class EstimatePreviewRequest(BaseModel):
    contractor: ContractorRatesIn
    province: Province
    code_edition: str
    assemblies: list[AssemblyRequestIn]
    additional_line_items: list[CustomLineItemIn] = Field(default_factory=list)
    material_markup_pct: Decimal | None = None
    labor_markup_pct: Decimal | None = None
    # Audit context:
    job_description: str = ""
    customer_facing_scope: str = ""
    customer_province: Province | None = None
    customer_language: str = "en"
    permit_date: date | None = None


class LineItemOut(BaseModel):
    line_number: int
    source: str
    assembly_id: str | None
    description_en: str
    description_fr: str
    quantity: Decimal
    materials_cost_cad: Decimal
    labor_hours: Decimal
    labor_cost_cad: Decimal
    line_total_cad: Decimal
    code_refs: list[dict]


class TaxOut(BaseModel):
    gst_cad: Decimal
    gst_rate: Decimal
    pst_qst_hst_cad: Decimal
    pst_qst_hst_rate: Decimal
    pst_qst_hst_label_en: str
    total_tax_cad: Decimal


class PreviewAuditFlagOut(BaseModel):
    severity: str
    code: str
    message_en: str
    message_fr: str
    suggested_action_en: str
    suggested_action_fr: str


class EstimatePreviewResponse(BaseModel):
    line_items: list[LineItemOut]
    subtotal_materials_cad: Decimal
    subtotal_labor_cad: Decimal
    subtotal_permits_cad: Decimal
    subtotal_other_cad: Decimal
    tax: TaxOut
    total_cad: Decimal
    gross_margin_pct: Decimal
    code_edition: str
    assumptions: list[str]
    audit_flags: list[PreviewAuditFlagOut]
    audit_passed: bool
    pdf_blocked: bool
