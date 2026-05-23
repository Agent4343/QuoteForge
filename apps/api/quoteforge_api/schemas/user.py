"""User (contractor) schemas (§13)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from quoteforge_api.models.enums import Language
from quoteforge_api.provinces import Province


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    business_name: str
    province: Province
    language: Language
    esa_license_number: str | None
    rbq_license_number: str | None
    cmeq_membership_number: str | None
    blended_labor_rate_cad: Decimal
    apprentice_labor_rate_cad: Decimal
    labor_cost_rate_cad: Decimal
    default_material_markup_pct: Decimal
    default_labor_markup_pct: Decimal
    minimum_callout_hours: Decimal
    minimum_margin_pct: Decimal
    logo_url: str | None
    primary_color_hex: str | None


class UserUpdate(BaseModel):
    """Partial update of business defaults, branding, and licensing (PATCH /me)."""

    full_name: str | None = Field(default=None, max_length=200)
    business_name: str | None = Field(default=None, max_length=200)
    province: Province | None = None
    language: Language | None = None
    esa_license_number: str | None = Field(default=None, max_length=60)
    rbq_license_number: str | None = Field(default=None, max_length=60)
    cmeq_membership_number: str | None = Field(default=None, max_length=60)
    blended_labor_rate_cad: Decimal | None = Field(default=None, ge=0)
    apprentice_labor_rate_cad: Decimal | None = Field(default=None, ge=0)
    labor_cost_rate_cad: Decimal | None = Field(default=None, ge=0)
    default_material_markup_pct: Decimal | None = Field(default=None, ge=0)
    default_labor_markup_pct: Decimal | None = Field(default=None, ge=0)
    minimum_callout_hours: Decimal | None = Field(default=None, ge=0)
    minimum_margin_pct: Decimal | None = Field(default=None, ge=0)
    logo_url: str | None = Field(default=None, max_length=500)
    primary_color_hex: str | None = Field(default=None, max_length=7)
