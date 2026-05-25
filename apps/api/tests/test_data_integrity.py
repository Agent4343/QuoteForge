"""Cross-file data-integrity checks (§8/§9).

Runs in CI via the existing ``pytest`` step, so a data edit that references a
non-existent SKU or an undeclared formula parameter fails the PR before merge.
"""

from __future__ import annotations

from quoteforge_api.assemblies.loader import AssemblyLibrary
from quoteforge_api.data_integrity import _formula_vars, validate_data


def test_shipped_data_is_internally_consistent(library, pricebook):
    # Every material SKU resolves and every qty_formula references a declared param.
    assert validate_data(library, pricebook) == []


def test_formula_vars_excludes_known_functions():
    assert _formula_vars("ceil(run_length_ft / 4)") == {"run_length_ft"}
    assert _formula_vars("max(a, b) + c * 2") == {"a", "b", "c"}


def test_validate_detects_bad_sku_and_undeclared_param(library, pricebook):
    base = library.get("circuit_new_15a_residential")
    broken = base.model_copy(update={"materials": [
        # qty_formula referencing a parameter the assembly doesn't declare
        base.materials[0].model_copy(update={"qty_formula": "bogus_param", "qty": None}),
        # a SKU that isn't in the price book
        base.materials[1].model_copy(update={"sku": "NOPE_SKU"}),
    ]})
    problems = validate_data(AssemblyLibrary({broken.id: broken}), pricebook)
    assert any("NOPE_SKU" in p for p in problems)
    assert any("bogus_param" in p for p in problems)
