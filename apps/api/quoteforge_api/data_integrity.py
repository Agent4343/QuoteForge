"""Cross-file data-integrity checks (§8, §9).

The Pydantic schema validates each assembly in isolation at load time, but it
can't see the price book or the formula evaluator. These checks catch the two
errors a reviewer is most likely to introduce while editing data:
  - a material SKU that doesn't exist in the price book, and
  - a ``qty_formula`` that references a parameter the assembly doesn't declare.
Both otherwise only blow up later, at estimate time. Gated in CI via
``tests/test_data_integrity.py``; also runnable with ``review_status --validate``.
"""

from __future__ import annotations

import ast

from quoteforge_api.assemblies.loader import AssemblyLibrary, get_library
from quoteforge_api.assemblies.schema import MaterialLine
from quoteforge_api.pricebook import PriceBook, get_pricebook
from quoteforge_api.services.estimating.formula import _FUNCS

_FORMULA_FUNCS = frozenset(_FUNCS)  # names that are functions, not parameters


def _formula_vars(expr: str) -> set[str]:
    """Parameter names referenced by a formula (excluding known functions)."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return set()  # syntax error is reported separately
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in _FORMULA_FUNCS
    }


def _material_problems(
    assembly_id: str, params: set[str], m: MaterialLine, where: str, pricebook: PriceBook
) -> list[str]:
    out: list[str] = []
    if m.sku not in pricebook:
        out.append(f"{assembly_id}: material SKU {m.sku!r} not in price book ({where})")
    if m.qty_formula is not None:
        try:
            ast.parse(m.qty_formula, mode="eval")
        except SyntaxError as exc:
            out.append(f"{assembly_id}: invalid qty_formula {m.qty_formula!r} ({where}): {exc}")
        else:
            undeclared = _formula_vars(m.qty_formula) - params
            if undeclared:
                out.append(
                    f"{assembly_id}: qty_formula references undeclared parameter(s) "
                    f"{sorted(undeclared)} ({where})"
                )
    return out


def validate_data(
    library: AssemblyLibrary | None = None, pricebook: PriceBook | None = None
) -> list[str]:
    """Return a sorted list of cross-file data problems ([] means clean)."""
    library = library or get_library()
    pricebook = pricebook or get_pricebook()
    problems: list[str] = []

    for a in library.all():
        params = set(a.parameters)
        for m in a.materials:
            problems.extend(_material_problems(a.id, params, m, "base", pricebook))
        for province, variant in a.provincial_variants.items():
            for m in variant.materials_override:
                problems.extend(
                    _material_problems(a.id, params, m, f"{province.value} override", pricebook)
                )
    return sorted(problems)
