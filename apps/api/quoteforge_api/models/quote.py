"""Quote, line item, audit flag, and LLM session models (§7).

Computed totals are written only by the estimating engine (principle §3.1) —
never by the LLM. Code/regulatory context is locked at quote time (§3.3/§3.4).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quoteforge_api.db import Base
from quoteforge_api.models.enums import FlagSeverity, Language, LineSource, QuoteStatus
from quoteforge_api.provinces import Province

_MONEY = sa.Numeric(12, 2)
_HOURS = sa.Numeric(8, 2)
_PCT = sa.Numeric(6, 2)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    quote_number: Mapped[str] = mapped_column(sa.String(30), index=True)
    status: Mapped[QuoteStatus] = mapped_column(
        sa.Enum(QuoteStatus, native_enum=False, length=12), default=QuoteStatus.DRAFT
    )

    # Job context.
    job_title: Mapped[str] = mapped_column(sa.String(300))
    job_description: Mapped[str] = mapped_column(sa.Text, default="")
    job_site_address: Mapped[str | None] = mapped_column(sa.String(400), nullable=True)

    # Code/regulatory context — locked at quote time.
    province: Mapped[Province] = mapped_column(sa.Enum(Province, native_enum=False, length=2))
    code_edition: Mapped[str] = mapped_column(sa.String(120), default="")
    permit_expected_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    # Computed totals — written by the estimating engine only.
    subtotal_materials_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    subtotal_labor_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    subtotal_permits_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    subtotal_other_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    tax_gst_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    tax_pst_qst_hst_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    total_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    gross_margin_pct: Mapped[Decimal] = mapped_column(_PCT, default=0)

    # AI / narrative metadata.
    customer_facing_scope_en: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    customer_facing_scope_fr: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    internal_notes: Mapped[str] = mapped_column(sa.Text, default="")
    audit_passed: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    audit_overrides: Mapped[dict] = mapped_column(sa.JSON, default=dict)

    valid_until: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    customer_language: Mapped[Language] = mapped_column(
        sa.Enum(Language, native_enum=False, length=2), default=Language.EN
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    line_items: Mapped[list[QuoteLineItem]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuoteLineItem.line_number"
    )
    audit_flags: Mapped[list[EstimateAuditFlag]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )

    __table_args__ = (sa.UniqueConstraint("user_id", "quote_number", name="uq_quote_number_per_user"),)


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(sa.Integer)
    source: Mapped[LineSource] = mapped_column(sa.Enum(LineSource, native_enum=False, length=10))
    assembly_id: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    description_en: Mapped[str] = mapped_column(sa.String(400))
    description_fr: Mapped[str] = mapped_column(sa.String(400))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), default=1)
    parameters: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    materials_cost_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    labor_hours: Mapped[Decimal] = mapped_column(_HOURS, default=0)
    labor_cost_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    line_total_cad: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    code_refs: Mapped[list] = mapped_column(sa.JSON, default=list)

    quote: Mapped[Quote] = relationship(back_populates="line_items")


class EstimateAuditFlag(Base):
    __tablename__ = "estimate_audit_flags"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[FlagSeverity] = mapped_column(
        sa.Enum(FlagSeverity, native_enum=False, length=10)
    )
    code: Mapped[str] = mapped_column(sa.String(60))
    message_en: Mapped[str] = mapped_column(sa.Text)
    message_fr: Mapped[str] = mapped_column(sa.Text)
    suggested_action: Mapped[str] = mapped_column(sa.Text, default="")
    overridden: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    overridden_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    quote: Mapped[Quote] = relationship(back_populates="audit_flags")


class LLMSession(Base):
    __tablename__ = "llm_sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    messages: Mapped[list] = mapped_column(sa.JSON, default=list)
    tool_calls: Mapped[list] = mapped_column(sa.JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    cost_cad: Mapped[Decimal] = mapped_column(sa.Numeric(10, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class RefreshToken(Base):
    """Hashed refresh tokens, rotated on use (§16)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
