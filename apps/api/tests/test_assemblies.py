"""Assembly loading, validation, and provincial-override behaviour."""

from decimal import Decimal

import pytest

from quoteforge_api.assemblies.loader import AssemblyLibrary
from quoteforge_api.assemblies.schema import Assembly, Status
from quoteforge_api.provinces import Province
from quoteforge_api.services.estimating import AssemblyRequest, ContractorRates, compute_estimate


def test_all_reference_assemblies_load(library):
    ids = {a.id for a in library.all()}
    assert {
        "recep_duplex_15a_residential",
        "recep_gfci_residential",
        "circuit_new_15a_residential",
        "pot_light_residential_remodel",
        "service_upgrade_200a_overhead",
        "ev_charger_l2_attached_garage",
    } <= ids


def test_draft_assemblies_excluded_from_llm_index(library):
    # All seeded assemblies are status=draft (no electrician sign-off yet, §8).
    assert library.llm_index() == []
    assert all(a.status == Status.DRAFT for a in library.all())


def test_unknown_assembly_raises(library):
    with pytest.raises(KeyError):
        library.get("does_not_exist")


_OVERRIDE_YAML = {
    "schema_version": "1.0",
    "id": "synthetic_override",
    "category": "devices",
    "trade": "electrical",
    "work_type": ["service"],
    "names": {"en": "Synthetic", "fr": "Synthétique"},
    "description": {"en": "x", "fr": "x"},
    "parameters": {},
    "materials": [
        {"sku": "RECEP_DUPLEX_15A", "qty": 1},
        {"sku": "BOX_DEVICE_PVC", "qty": 1},
    ],
    "labor": {"base_hours": 1.0, "phase": "trim", "minimum_callout_applies": False},
    "provincial_variants": {
        "ON": {"code_edition": "OESC"},
        "QC": {
            "code_edition_current": "Chapitre V",
            # Replace the box with a metal one and add a ground clamp.
            "materials_override": [
                {"sku": "BOX_DEVICE_PVC", "qty": 0},
                {"sku": "BOX_DEVICE_METAL", "qty": 1},
                {"sku": "GROUND_CLAMP", "qty": 1},
            ],
        },
    },
    "status": "draft",
}


def _lib_with_synthetic():
    return AssemblyLibrary({"synthetic_override": Assembly.model_validate(_OVERRIDE_YAML)})


def test_materials_override_changes_cost(pricebook):
    lib = _lib_with_synthetic()
    c = ContractorRates(Decimal("100"), Decimal("70"), Decimal("0"), Decimal("0"), Decimal("0"))
    on = compute_estimate(c, Province.ON, "OESC", [AssemblyRequest("synthetic_override")],
                          library=lib, pricebook=pricebook)
    qc = compute_estimate(c, Province.QC, "CV", [AssemblyRequest("synthetic_override")],
                          library=lib, pricebook=pricebook)
    # ON: recep 1.50 + pvc box 1.20 = 2.70 (0% markup).
    assert on.subtotal_materials_cad == Decimal("2.70")
    # QC: pvc box removed (qty 0), metal box 1.60 + ground clamp 4.50 added.
    #     recep 1.50 + metal 1.60 + clamp 4.50 = 7.60
    assert qc.subtotal_materials_cad == Decimal("7.60")


def test_qty_zero_removes_material(pricebook):
    # An override with qty 0 drops the base material from the expansion.
    yaml = dict(_OVERRIDE_YAML, id="synthetic_drop")
    yaml["provincial_variants"] = {
        "ON": {"code_edition": "OESC",
               "materials_override": [{"sku": "BOX_DEVICE_PVC", "qty": 0}]},
    }
    lib = AssemblyLibrary({"synthetic_drop": Assembly.model_validate(yaml)})
    c = ContractorRates(Decimal("100"), Decimal("70"), Decimal("0"), Decimal("0"), Decimal("0"))
    on = compute_estimate(c, Province.ON, "OESC", [AssemblyRequest("synthetic_drop")],
                          library=lib, pricebook=pricebook)
    # Only the receptacle remains: 1.50.
    assert on.subtotal_materials_cad == Decimal("1.50")
