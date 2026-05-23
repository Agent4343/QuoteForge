"""The estimating engine (§9). Pure Python, deterministic, fully unit-tested.

Principle §3.1: the LLM never does math. Every number a customer sees is
produced here. Build order inside the engine mirrors §9:

1. material expander  -> (sku, qty_after_waste) per assembly
2. labor calculator   -> base_hours x multipliers x qty, with minimum callout
3. permit lines       -> passed in as CustomLineItem(source='permit')
4. tax calculator     -> provincial rules (services/tax)
5. markup applier     -> contractor defaults, overridable per quote
6. margin computer    -> gross margin % on the marked-up assembly work
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from quoteforge_api.assemblies.loader import AssemblyLibrary, get_library
from quoteforge_api.assemblies.schema import Assembly, MaterialLine
from quoteforge_api.money import ZERO, D, money
from quoteforge_api.pricebook import PriceBook, get_pricebook
from quoteforge_api.provinces import Province
from quoteforge_api.services.estimating.formula import evaluate_formula
from quoteforge_api.services.estimating.types import (
    AssemblyRequest,
    ComputedLineItem,
    ContractorRates,
    CustomLineItem,
    EstimateResult,
)
from quoteforge_api.services.tax.engine import compute_taxes


def _resolve_params(assembly: Assembly, requested: dict[str, object]) -> dict[str, object]:
    """Merge requested parameters over assembly defaults; record nothing here."""
    resolved: dict[str, object] = {}
    for name, spec in assembly.parameters.items():
        resolved[name] = requested.get(name, spec.default)
    # Allow unrecognised params through (e.g. ad-hoc), they simply won't be used.
    for name, val in requested.items():
        resolved.setdefault(name, val)
    return resolved


def _effective_materials(assembly: Assembly, province: Province) -> list[MaterialLine]:
    """Apply a province's materials_override on top of the base list."""
    by_sku: dict[str, MaterialLine] = {m.sku: m for m in assembly.materials}
    variant = assembly.variant_for(province)
    if variant:
        for ov in variant.materials_override:
            by_sku[ov.sku] = ov
    return list(by_sku.values())


def _expand_materials(
    materials: list[MaterialLine], params: dict[str, object], pricebook: PriceBook
) -> Decimal:
    """Return the raw material cost for one unit of an assembly (pre-quantity)."""
    cost = ZERO
    for m in materials:
        if m.qty_formula is not None:
            qty = evaluate_formula(m.qty_formula, params)
        else:
            qty = D(m.qty)
        if qty <= ZERO:
            continue
        qty_after_waste = qty * (D(1) + D(m.waste))
        cost += qty_after_waste * pricebook.get(m.sku).cost_cad
    return cost


def _labor_multiplier(assembly: Assembly, params: dict[str, object]) -> Decimal:
    mult = D(1)
    for name, spec in assembly.parameters.items():
        if spec.labor_multipliers:
            value = params.get(name, spec.default)
            key = str(value)
            if key in spec.labor_multipliers:
                mult *= D(spec.labor_multipliers[key])
    return mult


def effective_materials(assembly: Assembly, province: Province) -> list[MaterialLine]:
    """Public wrapper around the province materials-override resolution (used by audit)."""
    return _effective_materials(assembly, province)


def unit_labor_hours(assembly: Assembly, params: dict[str, object], province: Province) -> Decimal:
    """Expected labour hours for one unit of an assembly, incl. province override
    and enum multipliers. Used by the audit's per-assembly plausibility check."""
    base_hours = assembly.labor.base_hours
    variant = assembly.variant_for(province)
    if variant and variant.labor_override and variant.labor_override.base_hours is not None:
        base_hours = variant.labor_override.base_hours
    return D(base_hours) * _labor_multiplier(assembly, params)


def compute_estimate(
    contractor: ContractorRates,
    province: Province,
    code_edition_at_permit_date: str,
    assemblies: list[AssemblyRequest],
    additional_line_items: list[CustomLineItem] | None = None,
    *,
    municipality: str | None = None,
    permit_date: date | None = None,
    material_markup_pct: Decimal | None = None,
    labor_markup_pct: Decimal | None = None,
    library: AssemblyLibrary | None = None,
    pricebook: PriceBook | None = None,
) -> EstimateResult:
    """Compute a complete estimate. Pure function, deterministic."""
    library = library or get_library()
    pricebook = pricebook or get_pricebook()
    additional_line_items = additional_line_items or []
    mat_markup = D(material_markup_pct if material_markup_pct is not None
                   else contractor.default_material_markup_pct)
    lab_markup = D(labor_markup_pct if labor_markup_pct is not None
                   else contractor.default_labor_markup_pct)
    rate = contractor.blended_labor_rate_cad

    assumptions: list[str] = []
    lines: list[ComputedLineItem] = []
    line_no = 0

    sub_materials = ZERO  # marked-up
    sub_labor = ZERO  # marked-up
    sub_permits = ZERO
    sub_other = ZERO
    raw_materials_total = ZERO
    raw_labor_total = ZERO
    total_labor_hours = ZERO
    callout_eligible = False

    for req in assemblies:
        assembly = library.get(req.assembly_id)
        params = _resolve_params(assembly, req.parameters)

        # Note any defaults applied for high-sensitivity params (assumption log).
        for name, spec in assembly.parameters.items():
            if name not in req.parameters and spec.sensitivity.value in {"medium", "high"}:
                assumptions.append(
                    f"{assembly.id}: assumed {name}={spec.default!r} (default)"
                )

        materials = _effective_materials(assembly, province)
        unit_material_cost = _expand_materials(materials, params, pricebook)
        raw_material_cost = unit_material_cost * req.quantity

        variant = assembly.variant_for(province)
        base_hours = assembly.labor.base_hours
        if variant and variant.labor_override and variant.labor_override.base_hours is not None:
            base_hours = variant.labor_override.base_hours
        unit_hours = D(base_hours) * _labor_multiplier(assembly, params)
        line_hours = unit_hours * req.quantity
        raw_labor_cost = line_hours * rate

        if assembly.labor.minimum_callout_applies:
            callout_eligible = True
        total_labor_hours += line_hours

        priced_materials = raw_material_cost * (D(1) + mat_markup / D(100))
        priced_labor = raw_labor_cost * (D(1) + lab_markup / D(100))
        line_total = money(priced_materials) + money(priced_labor)

        code_refs = [r.model_dump() for r in variant.code_refs] if variant else []

        lines.append(
            ComputedLineItem(
                line_number=(line_no := line_no + 1),
                source="assembly",
                assembly_id=assembly.id,
                description_en=assembly.names.en,
                description_fr=assembly.names.fr,
                quantity=req.quantity,
                parameters=params,
                materials_cost_cad=money(priced_materials),
                labor_hours=line_hours,
                labor_cost_cad=money(priced_labor),
                line_total_cad=line_total,
                code_refs=code_refs,
                raw_materials_cost_cad=money(raw_material_cost),
                raw_labor_cost_cad=money(raw_labor_cost),
                base_labor_hours=D(base_hours) * req.quantity,
            )
        )
        sub_materials += money(priced_materials)
        sub_labor += money(priced_labor)
        raw_materials_total += raw_material_cost
        raw_labor_total += raw_labor_cost

    # Custom + permit lines.
    for item in additional_line_items:
        total_labor_hours += item.labor_hours
        if item.source == "permit":
            sub_permits += item.amount_cad
            target_total = item.amount_cad
        else:
            sub_other += item.amount_cad
            target_total = item.amount_cad
        lines.append(
            ComputedLineItem(
                line_number=(line_no := line_no + 1),
                source=item.source,
                assembly_id=None,
                description_en=item.description_en,
                description_fr=item.description_fr,
                quantity=D(1),
                parameters={},
                materials_cost_cad=ZERO,
                labor_hours=item.labor_hours,
                labor_cost_cad=ZERO,
                line_total_cad=money(target_total),
                code_refs=item.code_refs,
            )
        )

    # Minimum callout: floor total billable labour for qualifying jobs (§9).
    if callout_eligible and total_labor_hours < contractor.minimum_callout_hours:
        uplift_hours = contractor.minimum_callout_hours - total_labor_hours
        uplift_cost = uplift_hours * rate
        priced_uplift = uplift_cost * (D(1) + lab_markup / D(100))
        lines.append(
            ComputedLineItem(
                line_number=(line_no := line_no + 1),
                source="custom",
                assembly_id=None,
                description_en="Minimum service call-out adjustment",
                description_fr="Ajustement pour appel de service minimum",
                quantity=D(1),
                parameters={},
                materials_cost_cad=ZERO,
                labor_hours=uplift_hours,
                labor_cost_cad=money(priced_uplift),
                line_total_cad=money(priced_uplift),
                code_refs=[],
                raw_labor_cost_cad=money(uplift_cost),
                base_labor_hours=uplift_hours,
                generated=True,
            )
        )
        sub_labor += money(priced_uplift)
        raw_labor_total += uplift_cost
        assumptions.append(
            f"Minimum service call-out of {contractor.minimum_callout_hours} hr applied."
        )

    sub_materials = money(sub_materials)
    sub_labor = money(sub_labor)
    sub_permits = money(sub_permits)
    sub_other = money(sub_other)

    # Tax: goods = materials; services = labour + custom 'other'. Permits untaxed.
    tax = compute_taxes(province, sub_materials, sub_labor + sub_other)

    total = money(sub_materials + sub_labor + sub_permits + sub_other + tax.total_tax_cad)

    # Gross margin on the marked-up assembly work (where we know cost). §10 audit.
    work_revenue = sub_materials + sub_labor
    work_cost = money(raw_materials_total + raw_labor_total)
    if work_revenue > ZERO:
        gross_margin_pct = ((work_revenue - work_cost) / work_revenue * D(100)).quantize(
            D("0.01")
        )
    else:
        gross_margin_pct = ZERO

    return EstimateResult(
        line_items=lines,
        subtotal_materials_cad=sub_materials,
        subtotal_labor_cad=sub_labor,
        subtotal_permits_cad=sub_permits,
        subtotal_other_cad=sub_other,
        tax=tax,
        total_cad=total,
        gross_margin_pct=gross_margin_pct,
        code_edition=code_edition_at_permit_date,
        assumptions=assumptions,
        total_cost_cad=work_cost,
    )
