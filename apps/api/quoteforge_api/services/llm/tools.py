"""Claude tool definitions and dispatch (§12).

Tools exposed to the model:
  - get_assembly_detail   read-only library lookup
  - compute_estimate      THE ONLY path to numbers (runs the deterministic engine)
  - lookup_permit_fees    static permit table
  - audit_estimate        runs the profit-protection audit
  - ask_contractor        pauses the flow for input (handled by the estimator loop)

The model never produces numbers or invents assembly ids / code references
(principles §3.1, §3.6; hard rules in the system prompt).
"""

from __future__ import annotations

from dataclasses import dataclass

from quoteforge_api.assemblies.loader import AssemblyLibrary
from quoteforge_api.models import Customer, Quote, User
from quoteforge_api.money import D
from quoteforge_api.pricebook import PriceBook
from quoteforge_api.services import quote_service
from quoteforge_api.services.estimating import AssemblyRequest, CustomLineItem
from quoteforge_api.services.estimating.permits import WorkCategory, lookup_permit_fee

ASK_CONTRACTOR = "ask_contractor"

TOOL_DEFS: list[dict] = [
    {
        "name": "get_assembly_detail",
        "description": (
            "Return full detail (parameters, materials, labour, and province-specific "
            "code references) for one or more assembly ids from the library."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assembly_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["assembly_ids"],
        },
    },
    {
        "name": "compute_estimate",
        "description": (
            "Compute the full estimate for the chosen assemblies and any additional "
            "line items. This is the ONLY way to get prices, labour, tax, and totals. "
            "It persists the result to the quote and runs the audit. Call it after you "
            "have resolved the assemblies and parameters. Set is_optional: true on "
            "recommended add-on work the customer can decline; optional items are "
            "priced separately and excluded from the project total and margin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assemblies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "assembly_id": {"type": "string"},
                            "quantity": {"type": "number"},
                            "parameters": {"type": "object"},
                            "is_optional": {"type": "boolean"},
                        },
                        "required": ["assembly_id"],
                    },
                },
                "additional_line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description_en": {"type": "string"},
                            "description_fr": {"type": "string"},
                            "amount_cad": {"type": "number"},
                            "source": {"type": "string", "enum": ["custom", "permit"]},
                            "labor_hours": {"type": "number"},
                            "is_optional": {"type": "boolean"},
                        },
                        "required": ["description_en", "description_fr", "amount_cad", "source"],
                    },
                },
            },
            "required": ["assemblies"],
        },
    },
    {
        "name": "lookup_permit_fees",
        "description": "Look up the permit fee for a province and work category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_category": {
                    "type": "string",
                    "enum": [c.value for c in WorkCategory],
                },
                "municipality": {"type": "string"},
                "amperage": {"type": "integer"},
            },
            "required": ["work_category"],
        },
    },
    {
        "name": "audit_estimate",
        "description": "Run the profit-protection audit on the current estimate and return flags.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": ASK_CONTRACTOR,
        "description": (
            "Pause and ask the contractor a single clarifying question. Only use for a "
            "high-sensitivity parameter where a default would shift the estimate by more "
            "than 10%. Maximum 4 questions per session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "affects_assemblies": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question", "why_it_matters"],
        },
    },
]


@dataclass
class ToolContext:
    quote: Quote
    user: User
    customer: Customer
    library: AssemblyLibrary
    pricebook: PriceBook
    include_draft: bool = False


def _assembly_detail(ctx: ToolContext, assembly_id: str) -> dict:
    if assembly_id not in ctx.library.indexable(ctx.include_draft):
        return {"error": f"unknown or unavailable assembly id: {assembly_id!r}"}
    a = ctx.library.get(assembly_id)
    variant = a.variant_for(ctx.quote.province)
    return {
        "id": a.id,
        "category": a.category.value,
        "names": {"en": a.names.en, "fr": a.names.fr},
        "description": {"en": a.description.en, "fr": a.description.fr},
        "parameters": {
            name: {
                "type": p.type.value,
                "default": p.default,
                "values": p.values,
                "sensitivity": p.sensitivity.value,
                "prompt_en": p.prompt_en,
            }
            for name, p in a.parameters.items()
        },
        "province_variant": None
        if variant is None
        else {
            "code_edition": variant.resolved_code_edition(),
            "code_refs": [r.model_dump() for r in variant.code_refs],
            "permit_handling": variant.permit_handling,
        },
    }


def _compute_estimate(ctx: ToolContext, payload: dict) -> dict:
    allowed = ctx.library.indexable(ctx.include_draft)
    assemblies: list[AssemblyRequest] = []
    for item in payload.get("assemblies", []):
        aid = item.get("assembly_id")
        if aid not in allowed:
            return {"error": f"unknown assembly id {aid!r}. Do not invent ids; "
                             "add unknown work as an additional custom line item instead."}
        assemblies.append(
            AssemblyRequest(
                aid,
                item.get("quantity", 1),
                item.get("parameters", {}) or {},
                is_optional=bool(item.get("is_optional", False)),
            )
        )
    extras = [
        CustomLineItem(
            description_en=i["description_en"],
            description_fr=i["description_fr"],
            amount_cad=i["amount_cad"],
            source=i.get("source", "custom"),
            labor_hours=i.get("labor_hours", 0),
            is_optional=bool(i.get("is_optional", False)),
        )
        for i in payload.get("additional_line_items", []) or []
    ]
    quote_service.apply_estimate(ctx.quote, ctx.user, ctx.customer, assemblies, extras)
    return _estimate_summary(ctx.quote)


def _estimate_summary(quote: Quote) -> dict:
    optional_subtotal = sum(
        (li.line_total_cad for li in quote.line_items if li.is_optional), D(0)
    )
    return {
        "subtotal_materials_cad": str(quote.subtotal_materials_cad),
        "subtotal_labor_cad": str(quote.subtotal_labor_cad),
        "subtotal_permits_cad": str(quote.subtotal_permits_cad),
        "subtotal_other_cad": str(quote.subtotal_other_cad),
        "tax_gst_cad": str(quote.tax_gst_cad),
        "tax_pst_qst_hst_cad": str(quote.tax_pst_qst_hst_cad),
        "total_cad": str(quote.total_cad),
        "gross_margin_pct": str(quote.gross_margin_pct),
        "optional_subtotal_cad": str(optional_subtotal),
        "line_items": [
            {
                "description_en": li.description_en,
                "quantity": str(li.quantity),
                "line_total_cad": str(li.line_total_cad),
                "is_optional": li.is_optional,
            }
            for li in quote.line_items
        ],
        "audit": _audit_summary(quote),
    }


def _audit_summary(quote: Quote) -> dict:
    return {
        "passed": quote_service.pdf_blocked(quote) is False,
        "pdf_blocked": quote_service.pdf_blocked(quote),
        "flags": [
            {"severity": f.severity.value, "code": f.code, "message_en": f.message_en}
            for f in quote.audit_flags
        ],
    }


def _lookup_permit(ctx: ToolContext, payload: dict) -> dict:
    try:
        category = WorkCategory(payload["work_category"])
    except ValueError:
        return {"error": f"unknown work_category {payload.get('work_category')!r}"}
    fee = lookup_permit_fee(
        ctx.quote.province, category, payload.get("municipality"), payload.get("amperage")
    )
    if fee is None:
        return {"fee_cad": None, "note": "No permit fee on file for this province/category."}
    return {
        "fee_cad": str(fee.fee_cad),
        "description_en": fee.description_en,
        "description_fr": fee.description_fr,
        "province": fee.province.value,
        "work_category": fee.work_category.value,
    }


def execute_tool(ctx: ToolContext, name: str, payload: dict) -> dict:
    """Execute a non-pausing tool and return a JSON-serializable result.

    ``ask_contractor`` is never dispatched here — the estimator loop intercepts
    it to pause for human input.
    """
    if name == "get_assembly_detail":
        return {"assemblies": [_assembly_detail(ctx, a) for a in payload.get("assembly_ids", [])]}
    if name == "compute_estimate":
        return _compute_estimate(ctx, payload)
    if name == "lookup_permit_fees":
        return _lookup_permit(ctx, payload)
    if name == "audit_estimate":
        return _audit_summary(ctx.quote)
    return {"error": f"unknown tool {name!r}"}
