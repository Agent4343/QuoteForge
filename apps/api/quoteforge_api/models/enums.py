"""Database-level enums (§7)."""

from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    FR = "fr"


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"


class LineSource(StrEnum):
    ASSEMBLY = "assembly"
    CUSTOM = "custom"
    PERMIT = "permit"


class FlagSeverity(StrEnum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"
