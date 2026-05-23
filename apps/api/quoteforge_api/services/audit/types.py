"""Types for the profit-protection audit engine (§10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from quoteforge_api.assemblies.loader import AssemblyLibrary
from quoteforge_api.pricebook import PriceBook
from quoteforge_api.provinces import Province
from quoteforge_api.services.estimating.types import AssemblyRequest, EstimateResult


@dataclass(frozen=True)
class AuditFlag:
    severity: str  # info | warn | critical
    code: str  # machine-readable, e.g. "MARGIN_BELOW_MIN"
    message_en: str
    message_fr: str
    suggested_action_en: str
    suggested_action_fr: str

    @property
    def blocks_pdf(self) -> bool:
        # Critical flags block PDF generation until explicitly overridden (§3.5, §10).
        return self.severity == "critical"


@dataclass
class AuditContext:
    estimate: EstimateResult
    contractor_minimum_margin_pct: Decimal
    province: Province
    requested_assemblies: list[AssemblyRequest]
    library: AssemblyLibrary
    pricebook: PriceBook
    job_description: str = ""
    customer_facing_scope: str = ""
    customer_province: Province | None = None
    customer_language: str = "en"  # en | fr
    permit_date: date | None = None
    as_of: date | None = None  # for stale-pricing check; defaults to today
    line_hours_override: dict[int, Decimal] = field(default_factory=dict)
    # ^ optional: contractor-edited labour hours keyed by line_number, so the
    #   plausibility check can compare edits against engine-expected hours.
