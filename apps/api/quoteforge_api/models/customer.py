"""Customer model (§7). Per-contractor; isolation enforced in the repository layer."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from quoteforge_api.db import Base
from quoteforge_api.provinces import Province


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(sa.String(200))
    company: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(sa.String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    address_line1: Mapped[str] = mapped_column(sa.String(200))
    address_line2: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    city: Mapped[str] = mapped_column(sa.String(120))
    province: Mapped[Province] = mapped_column(sa.Enum(Province, native_enum=False, length=2))
    postal_code: Mapped[str] = mapped_column(sa.String(10))
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
