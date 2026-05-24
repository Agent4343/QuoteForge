"""User (contractor) model (§7). Single-tenant per contractor; no team accounts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from quoteforge_api.db import Base
from quoteforge_api.models.enums import Language
from quoteforge_api.provinces import Province


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    full_name: Mapped[str] = mapped_column(sa.String(200))
    business_name: Mapped[str] = mapped_column(sa.String(200))
    province: Mapped[Province] = mapped_column(sa.Enum(Province, native_enum=False, length=2))
    language: Mapped[Language] = mapped_column(
        sa.Enum(Language, native_enum=False, length=2), default=Language.EN
    )

    # Licensing (province-dependent, all optional).
    esa_license_number: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)
    rbq_license_number: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)
    cmeq_membership_number: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)

    # Business defaults.
    blended_labor_rate_cad: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=0)
    apprentice_labor_rate_cad: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=0)
    # Loaded labour COST per hour (margin basis). 0 -> use the billed blended rate.
    labor_cost_rate_cad: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=0, server_default="0")
    default_material_markup_pct: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=35)
    default_labor_markup_pct: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=0)
    minimum_callout_hours: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=1)
    minimum_margin_pct: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=20)

    # Business contact details for the PDF header (§14). Province uses `province` above.
    business_email: Mapped[str | None] = mapped_column(sa.String(320), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    business_address_line1: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    business_address_line2: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    business_city: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    business_postal_code: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)

    # Branding.
    logo_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    primary_color_hex: Mapped[str | None] = mapped_column(sa.String(7), nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
