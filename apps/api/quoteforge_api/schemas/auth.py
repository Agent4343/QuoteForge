"""Auth request/response schemas (§13, §16)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from quoteforge_api.models.enums import Language
from quoteforge_api.provinces import Province


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    business_name: str = Field(min_length=1, max_length=200)
    province: Province
    language: Language | None = None  # defaults per province (QC -> fr)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=200)
