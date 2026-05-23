"""Estimating engine reference fixtures (§9, §20, §21).

Each case below is a deterministic reference estimate. CI fails if any total
drifts (§9: "CI fails if any reference estimate drifts"). Two cases are also
hand-verified in comments; the remainder lock current engine behaviour against
the version-controlled YAML + price book.

NOTE: the underlying labour hours and material prices are PLACEHOLDERS. §21
requires an electrician to verify the input values before launch. These tests
guard the engine math, not the business accuracy of the inputs.
"""

from decimal import Decimal

from quoteforge_api.provinces import Province
from quoteforge_api.services.estimating import (
    AssemblyRequest,
    CustomLineItem,
    compute_estimate,
)
from quoteforge_api.services.estimating.permits import WorkCategory, lookup_permit_fee


def D(s: str) -> Decimal:
    return Decimal(s)


def _estimate(contractor, library, pricebook, province, assemblies, extra=None, **kw):
    return compute_estimate(
        contractor,
        province,
        kw.pop("code_edition", "OESC 2024 (28th)"),
        assemblies,
        extra,
        library=library,
        pricebook=pricebook,
        **kw,
    )


def test_single_receptacle_ontario_hand_verified(contractor, library, pricebook):
    # Materials cost: recep 1.50 + box 1.20 + plate 0.75 + wire 16.5ft*0.55=9.075
    #   + 4*0.12=0.48 + staples ceil(15/4)=4*0.06=0.24 + connector 0.35 = 13.595
    # Marked up 35% -> 18.35. Labour 0.5h, but 1h minimum call-out -> 1.0h*110=110.
    # HST 13% on (18.35+110)=128.35 -> 16.69. Total 145.04.
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("recep_duplex_15a_residential", D("1"),
                         {"cable_run_ft": 15, "mount_type": "standard"})],
    )
    assert r.subtotal_materials_cad == D("18.35")
    assert r.subtotal_labor_cad == D("110.00")
    assert r.tax.pst_qst_hst_cad == D("16.69")
    assert r.total_cad == D("145.04")
    assert any("Minimum service call-out" in a for a in r.assumptions)


def test_new_circuit_ontario_hand_verified(contractor, library, pricebook):
    # Wire 40*1.10=44ft*0.55=24.20; breaker 7; box 1.20; recep 1.50; plate 0.75;
    # staples ceil(40/4)=10*0.06=0.60; 4 connectors 0.48; 2 NM conn 0.70 = 36.43
    # *1.35 = 49.18. Labour 1.5h*110=165 (over minimum). HST 13% of 214.18=27.84.
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("circuit_new_15a_residential", D("1"),
                         {"run_length_ft": 40, "access": "open"})],
    )
    assert r.subtotal_materials_cad == D("49.18")
    assert r.subtotal_labor_cad == D("165.00")
    assert r.tax.pst_qst_hst_cad == D("27.84")
    assert r.total_cad == D("242.02")


def test_gfci_oldwork_labor_multiplier(contractor, library, pricebook):
    # old_work multiplier 1.4 on 0.65h = 0.91h -> over 1h? no, 0.91 < 1 -> callout to 1h.
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("recep_gfci_residential", D("1"),
                         {"cable_run_ft": 20, "mount_type": "old_work"})],
    )
    assert r.subtotal_materials_cad == D("44.79")
    assert r.subtotal_labor_cad == D("110.00")
    assert r.total_cad == D("174.91")


def test_six_pot_lights_quantity_scaling(contractor, library, pricebook):
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("pot_light_residential_remodel", D("6"),
                         {"inter_fixture_ft": 8, "ceiling_access": "attic_above"})],
    )
    assert r.subtotal_materials_cad == D("159.33")
    assert r.subtotal_labor_cad == D("495.00")  # 0.75h*6=4.5h*110
    assert r.total_cad == D("739.39")


def test_service_upgrade_ontario_with_permit(contractor, library, pricebook):
    permit = lookup_permit_fee(Province.ON, WorkCategory.SERVICE_CHANGE)
    extra = [CustomLineItem(permit.description_en, permit.description_fr,
                            permit.fee_cad, "permit")]
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("service_upgrade_200a_overhead", D("1"),
                         {"service_entrance_ft": 12, "ground_run_ft": 25,
                          "panel_location": "same_spot"})],
        extra=extra,
    )
    assert r.subtotal_materials_cad == D("794.31")
    assert r.subtotal_labor_cad == D("880.00")  # 8h*110
    assert r.subtotal_permits_cad == D("132.00")
    # Permit is not taxed: HST base is materials+labour only.
    assert r.tax.pst_qst_hst_cad == D("217.66")
    assert r.total_cad == D("2023.97")


def test_service_upgrade_quebec_labor_override_and_taxes(contractor, library, pricebook):
    # QC labor_override -> 9h. GST 5% + QST 9.975%, both on materials+labour.
    r = _estimate(
        contractor, library, pricebook, Province.QC,
        [AssemblyRequest("service_upgrade_200a_overhead", D("1"),
                         {"service_entrance_ft": 12, "ground_run_ft": 25,
                          "panel_location": "same_spot"})],
        code_edition="Chapitre V (CCÉ 2015 + modifications QC)",
    )
    assert r.subtotal_labor_cad == D("990.00")  # 9h*110
    assert r.tax.gst_cad == D("89.22")
    assert r.tax.pst_qst_hst_cad == D("177.98")
    assert r.total_cad == D("2051.51")


def test_ev_charger_ontario(contractor, library, pricebook):
    r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("ev_charger_l2_attached_garage", D("1"),
                         {"wire_run_ft": 30, "routing": "open"})],
    )
    assert r.subtotal_materials_cad == D("228.02")
    assert r.subtotal_labor_cad == D("330.00")  # 3h*110
    assert r.total_cad == D("630.56")


def test_finished_routing_multiplier_increases_labor(contractor, library, pricebook):
    open_r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("ev_charger_l2_attached_garage", D("1"),
                         {"wire_run_ft": 30, "routing": "open"})],
    )
    fin_r = _estimate(
        contractor, library, pricebook, Province.ON,
        [AssemblyRequest("ev_charger_l2_attached_garage", D("1"),
                         {"wire_run_ft": 30, "routing": "finished"})],
    )
    # 1.5x labour multiplier.
    assert fin_r.subtotal_labor_cad == open_r.subtotal_labor_cad * D("1.5")


def test_labor_markup_increases_margin(library, pricebook):
    from quoteforge_api.services.estimating import ContractorRates
    base = ContractorRates(D("110"), D("70"), D("35"), D("0"), D("1"))
    with_markup = ContractorRates(D("110"), D("70"), D("35"), D("25"), D("1"))
    a = compute_estimate(base, Province.ON, "OESC", [AssemblyRequest(
        "circuit_new_15a_residential", D("1"), {"run_length_ft": 40, "access": "open"})],
        library=library, pricebook=pricebook)
    b = compute_estimate(with_markup, Province.ON, "OESC", [AssemblyRequest(
        "circuit_new_15a_residential", D("1"), {"run_length_ft": 40, "access": "open"})],
        library=library, pricebook=pricebook)
    assert b.gross_margin_pct > a.gross_margin_pct
    assert b.subtotal_labor_cad == D("206.25")  # 165 * 1.25


def test_per_quote_markup_override(contractor, library, pricebook):
    r = compute_estimate(
        contractor, Province.ON, "OESC",
        [AssemblyRequest("circuit_new_15a_residential", D("1"),
                         {"run_length_ft": 40, "access": "open"})],
        material_markup_pct=D("50"),
        library=library, pricebook=pricebook,
    )
    # raw material 36.43 * 1.50 = 54.645 -> 54.65
    assert r.subtotal_materials_cad == D("54.65")


def test_deterministic_repeatable(contractor, library, pricebook):
    args = (Province.ON, [AssemblyRequest("ev_charger_l2_attached_garage", D("1"),
                                          {"wire_run_ft": 30, "routing": "open"})])
    r1 = _estimate(contractor, library, pricebook, *args)
    r2 = _estimate(contractor, library, pricebook, *args)
    assert r1.total_cad == r2.total_cad == D("630.56")


def test_labor_cost_rate_below_billed_raises_margin(library, pricebook):
    from quoteforge_api.services.estimating import ContractorRates
    job = [AssemblyRequest("circuit_new_15a_residential", D("1"),
                           {"run_length_ft": 40, "access": "open"})]
    # Same billed rate ($110) so the customer total is unchanged; a $70 cost rate
    # attributes labour profit and lifts the margin.
    billed_eq_cost = ContractorRates(D("110"), D("70"), D("35"), D("0"), D("1"))
    with_cost = ContractorRates(
        D("110"), D("70"), D("35"), D("0"), D("1"), labor_cost_rate_cad=D("70")
    )
    a = compute_estimate(billed_eq_cost, Province.ON, "x", job, library=library, pricebook=pricebook)
    b = compute_estimate(with_cost, Province.ON, "x", job, library=library, pricebook=pricebook)
    assert a.total_cad == b.total_cad == D("242.02")  # customer total identical
    assert b.gross_margin_pct > a.gross_margin_pct
    assert b.gross_margin_pct > D("20")  # now clears a typical 20% minimum
