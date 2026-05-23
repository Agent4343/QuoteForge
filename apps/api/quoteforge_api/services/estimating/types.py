"""Input/output types for the estimating engine (§9).

These are plain dataclasses, deliberately decoupled from the SQLAlchemy models
so the engine stays a pure, unit-testable function. The API layer maps DB rows
into these and persists the results back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from quoteforge_api.money import D
from quoteforge_api.services.tax.engine import TaxBreakdown


@dataclass(frozen=True)
class ContractorRates:
    """The subset of contractor settings the engine needs (§7 User fields)."""

    blended_labor_rate_cad: Decimal
    apprentice_labor_rate_cad: Decimal
    default_material_markup_pct: Decimal
    default_labor_markup_pct: Decimal
    minimum_callout_hours: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "blended_labor_rate_cad", D(self.blended_labor_rate_cad))
        object.__setattr__(self, "apprentice_labor_rate_cad", D(self.apprentice_labor_rate_cad))
        object.__setattr__(
            self, "default_material_markup_pct", D(self.default_material_markup_pct)
        )
        object.__setattr__(self, "default_labor_markup_pct", D(self.default_labor_markup_pct))
        object.__setattr__(self, "minimum_callout_hours", D(self.minimum_callout_hours))


@dataclass
class AssemblyRequest:
    assembly_id: str
    quantity: Decimal = D(1)
    parameters: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.quantity = D(self.quantity)


@dataclass
class CustomLineItem:
    """A line the contractor adds outside the assembly library.

    ``source='permit'`` → pass-through government fee (no markup, no tax).
    ``source='custom'`` → contractor-confirmed price for extra work (taxed as a
    service, no markup applied — the amount is already a final price).
    """

    description_en: str
    description_fr: str
    amount_cad: Decimal
    source: str = "custom"  # custom | permit
    labor_hours: Decimal = D(0)
    code_refs: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.amount_cad = D(self.amount_cad)
        self.labor_hours = D(self.labor_hours)


@dataclass
class ComputedLineItem:
    line_number: int
    source: str  # assembly | custom | permit
    assembly_id: str | None
    description_en: str
    description_fr: str
    quantity: Decimal
    parameters: dict[str, object]
    # Customer-facing (marked-up) amounts:
    materials_cost_cad: Decimal
    labor_hours: Decimal
    labor_cost_cad: Decimal
    line_total_cad: Decimal
    code_refs: list[dict]
    # Internal cost basis (for margin + audit), not shown to the customer:
    raw_materials_cost_cad: Decimal = D(0)
    raw_labor_cost_cad: Decimal = D(0)
    base_labor_hours: Decimal = D(0)  # assembly base hours × qty, pre-multipliers
    generated: bool = False  # True for engine-synthesised lines (e.g. minimum call-out)


@dataclass
class EstimateResult:
    line_items: list[ComputedLineItem]
    subtotal_materials_cad: Decimal
    subtotal_labor_cad: Decimal
    subtotal_permits_cad: Decimal
    subtotal_other_cad: Decimal
    tax: TaxBreakdown
    total_cad: Decimal
    gross_margin_pct: Decimal
    code_edition: str
    assumptions: list[str] = field(default_factory=list)
    # Internal cost totals (for the audit engine):
    total_cost_cad: Decimal = D(0)
