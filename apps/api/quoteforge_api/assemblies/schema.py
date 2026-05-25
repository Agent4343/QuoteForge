"""Assembly YAML schema (§8). Validated with Pydantic v2 at load time.

Assemblies are the product (principle §3.2). The schema is intentionally strict
so a malformed YAML file fails loudly at startup rather than producing a wrong
estimate later.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from quoteforge_api.provinces import Province


class Category(StrEnum):
    SERVICE = "service"
    PANELS = "panels"
    CIRCUITS = "circuits"
    DEVICES = "devices"
    LIGHTING = "lighting"
    EV = "ev"
    SAFETY = "safety"
    EXTERIOR = "exterior"
    TROUBLESHOOTING = "troubleshooting"
    SPECIAL = "special"


class WorkType(StrEnum):
    SERVICE = "service"
    RENOVATION = "renovation"
    NEW_CONSTRUCTION = "new_construction"


class ParamType(StrEnum):
    NUMBER = "number"
    ENUM = "enum"
    BOOLEAN = "boolean"


class Sensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Phase(StrEnum):
    ROUGH_IN = "rough_in"
    TRIM = "trim"
    SERVICE = "service"
    SPECIAL = "special"


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class Status(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LocalizedText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    en: str
    fr: str


class Parameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: ParamType
    default: object | None = None
    values: list[str] | None = None
    sensitivity: Sensitivity = Sensitivity.LOW
    prompt_en: str | None = None
    prompt_fr: str | None = None
    labor_multipliers: dict[str, Decimal] | None = None

    @model_validator(mode="after")
    def _check_enum(self) -> Parameter:
        if self.type == ParamType.ENUM and not self.values:
            raise ValueError("enum parameter must declare `values`")
        if self.labor_multipliers:
            for v in self.labor_multipliers:
                if self.values and v not in self.values:
                    raise ValueError(
                        f"labor_multiplier key {v!r} not in declared values {self.values}"
                    )
        return self


class MaterialLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    qty: Decimal | None = None
    qty_formula: str | None = None
    waste: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    @model_validator(mode="after")
    def _check_qty(self) -> MaterialLine:
        if (self.qty is None) == (self.qty_formula is None):
            raise ValueError(f"material {self.sku}: set exactly one of `qty` or `qty_formula`")
        return self


class Labor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_hours: Decimal = Field(ge=0)
    phase: Phase
    apprentice_compatible: bool = False
    minimum_callout_applies: bool = False


class CodeRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    note: str


class LaborOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_hours: Decimal | None = Field(default=None, ge=0)


class ProvincialVariant(BaseModel):
    # Permissive: ON and QC carry different fields (QC has transition metadata).
    model_config = ConfigDict(extra="allow")
    code_edition: str | None = None
    code_edition_current: str | None = None
    code_edition_pending: str | None = None
    transition_period_until: str | None = None
    code_refs: list[CodeRef] = Field(default_factory=list)
    materials_override: list[MaterialLine] = Field(default_factory=list)
    labor_override: LaborOverride | None = None
    permit_handling: str | None = None
    customer_language_default: str | None = None

    def resolved_code_edition(self) -> str:
        return self.code_edition or self.code_edition_current or ""


class AuditFlagSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition: str
    severity: Severity
    message_en: str
    message_fr: str


class Assembly(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    id: str
    category: Category
    trade: str = "electrical"
    work_type: list[WorkType]
    names: LocalizedText
    description: LocalizedText
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    materials: list[MaterialLine] = Field(default_factory=list)
    labor: Labor
    provincial_variants: dict[Province, ProvincialVariant] = Field(default_factory=dict)
    audit_flags: list[AuditFlagSpec] = Field(default_factory=list)
    last_reviewed: str | None = None
    reviewed_by: str | None = None
    status: Status = Status.DRAFT
    # Confidence metadata (§24.6) — set by reviewers; safe defaults until then, so
    # derived confidence stays honest (everything is "unreviewed" out of the gate).
    review_count: int = Field(default=0, ge=0)
    provinces_reviewed: list[Province] = Field(default_factory=list)
    last_field_validation: str | None = None
    customer_risk: RiskLevel = RiskLevel.LOW

    def variant_for(self, province: Province) -> ProvincialVariant | None:
        return self.provincial_variants.get(province)
