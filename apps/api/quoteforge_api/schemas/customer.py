"""Customer schemas (§13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from quoteforge_api.provinces import Province


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line1: str = Field(min_length=1, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    province: Province
    postal_code: str = Field(min_length=1, max_length=10)
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    province: Province | None = None
    postal_code: str | None = Field(default=None, max_length=10)
    notes: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company: str | None
    email: str | None
    phone: str | None
    address_line1: str
    address_line2: str | None
    city: str
    province: Province
    postal_code: str
    notes: str | None
    created_at: datetime
