"""Quote schemas (§13). Computed totals are output-only; clients never set them."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from quoteforge_api.models.enums import FlagSeverity, Language, LineSource, QuoteStatus
from quoteforge_api.provinces import Province


class QuoteLineItemIn(BaseModel):
    """A contractor-specified input line. Computed costs are filled by the engine."""

    source: LineSource = LineSource.ASSEMBLY
    assembly_id: str | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    parameters: dict[str, object] = Field(default_factory=dict)
    # For custom / permit lines (contractor-confirmed price):
    description_en: str | None = None
    description_fr: str | None = None
    amount_cad: Decimal | None = Field(default=None, ge=0)
    labor_hours: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def _check(self) -> QuoteLineItemIn:
        if self.source == LineSource.ASSEMBLY:
            if not self.assembly_id:
                raise ValueError("assembly line requires assembly_id")
        else:
            if self.amount_cad is None or not self.description_en or not self.description_fr:
                raise ValueError(
                    "custom/permit line requires description_en, description_fr, amount_cad"
                )
        return self


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    job_title: str = Field(min_length=1, max_length=300)
    job_description: str = ""
    job_site_address: str | None = Field(default=None, max_length=400)
    province: Province | None = None  # defaults to the customer's province
    code_edition: str | None = None
    permit_expected_date: date | None = None
    customer_language: Language | None = None  # defaults per province (QC -> fr)
    valid_until: date | None = None  # defaults to +30 days
    line_items: list[QuoteLineItemIn] = Field(default_factory=list)


class QuoteUpdate(BaseModel):
    job_title: str | None = Field(default=None, max_length=300)
    job_description: str | None = None
    job_site_address: str | None = Field(default=None, max_length=400)
    code_edition: str | None = None
    permit_expected_date: date | None = None
    customer_language: Language | None = None
    valid_until: date | None = None
    internal_notes: str | None = None
    customer_facing_scope_en: str | None = None
    customer_facing_scope_fr: str | None = None
    line_items: list[QuoteLineItemIn] | None = None  # if provided, replaces the set


class QuoteLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_number: int
    source: LineSource
    assembly_id: str | None
    description_en: str
    description_fr: str
    quantity: Decimal
    parameters: dict
    materials_cost_cad: Decimal
    labor_hours: Decimal
    labor_cost_cad: Decimal
    line_total_cad: Decimal
    code_refs: list


class AuditFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: FlagSeverity
    code: str
    message_en: str
    message_fr: str
    suggested_action: str
    overridden: bool
    overridden_at: datetime | None


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    quote_number: str
    status: QuoteStatus
    job_title: str
    job_description: str
    job_site_address: str | None
    province: Province
    code_edition: str
    permit_expected_date: date | None
    subtotal_materials_cad: Decimal
    subtotal_labor_cad: Decimal
    subtotal_permits_cad: Decimal
    subtotal_other_cad: Decimal
    tax_gst_cad: Decimal
    tax_pst_qst_hst_cad: Decimal
    total_cad: Decimal
    gross_margin_pct: Decimal
    customer_facing_scope_en: str | None
    customer_facing_scope_fr: str | None
    internal_notes: str
    audit_passed: bool
    valid_until: date | None
    customer_language: Language
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    approved_at: datetime | None
    line_items: list[QuoteLineItemOut]
    audit_flags: list[AuditFlagOut]
    pdf_blocked: bool = False


class QuoteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quote_number: str
    status: QuoteStatus
    job_title: str
    total_cad: Decimal
    gross_margin_pct: Decimal
    created_at: datetime


class OverrideFlagRequest(BaseModel):
    flag_id: uuid.UUID


class MarkStatusRequest(BaseModel):
    status: QuoteStatus
