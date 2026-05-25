"""Audit engine tests (§10, §21).

§21 Definition of Done: "The audit catches a deliberately underbid quote in
100% of test cases." Covered by test_underbid_quote_always_flagged_critical.
"""

from datetime import date
from decimal import Decimal

from quoteforge_api.provinces import Province
from quoteforge_api.services.audit import AuditContext, run_audit
from quoteforge_api.services.audit.rules import (
    afci_required_for_new_circuits_in_dwelling,
    customer_supplied_equipment_check,
    hq_coordination_for_qc_service_changes,
    labor_hours_outside_band_per_assembly,
    margin_below_minimum,
    qc_code_edition_transition_warning,
    qc_customer_language_check,
    requires_permit_when_service_change,
    scope_creep_language_in_description,
    service_capacity_verification,
    stale_material_pricing,
    travel_time_for_long_jobs,
    utility_locate_required,
)
from quoteforge_api.services.estimating import (
    AssemblyRequest,
    ContractorRates,
    CustomLineItem,
    compute_estimate,
)
from quoteforge_api.services.estimating.permits import WorkCategory, lookup_permit_fee


def D(s: str) -> Decimal:
    return Decimal(s)


def _ctx(estimate, assemblies, library, pricebook, *, province=Province.ON,
         min_margin="20", **kw):
    return AuditContext(
        estimate=estimate,
        contractor_minimum_margin_pct=D(min_margin),
        province=province,
        requested_assemblies=assemblies,
        library=library,
        pricebook=pricebook,
        as_of=date(2026, 5, 23),
        **kw,
    )


def _estimate(contractor, library, pricebook, province, assemblies, extra=None, **kw):
    return compute_estimate(contractor, province, "OESC 2024 (28th)", assemblies, extra,
                            library=library, pricebook=pricebook, **kw)


def codes(result):
    return {f.code for f in result.flags}


# --- the headline profit-protection requirement (§21) -----------------------

def test_underbid_quote_always_flagged_critical(library, pricebook):
    """Deliberately underbid: near-zero markup against a 20% minimum margin.
    Across several job types this must ALWAYS raise a blocking critical flag."""
    underbid = ContractorRates(D("110"), D("70"), D("0"), D("0"), D("1"))
    jobs = [
        [AssemblyRequest("recep_duplex_15a_residential", D("1"), {"cable_run_ft": 15})],
        [AssemblyRequest("circuit_new_15a_residential", D("1"), {"run_length_ft": 40})],
        [AssemblyRequest("ev_charger_l2_attached_garage", D("1"), {"wire_run_ft": 30})],
        [AssemblyRequest("pot_light_residential_remodel", D("6"), {"inter_fixture_ft": 8})],
    ]
    for assemblies in jobs:
        est = _estimate(underbid, library, pricebook, Province.ON, assemblies)
        result = run_audit(_ctx(est, assemblies, library, pricebook, min_margin="20"))
        assert result.blocks_pdf, f"underbid not caught for {assemblies[0].assembly_id}"
        assert "MARGIN_BELOW_MIN" in codes(result)


def test_healthy_margin_does_not_block(library, pricebook):
    healthy = ContractorRates(D("110"), D("70"), D("60"), D("60"), D("1"))
    assemblies = [AssemblyRequest("circuit_new_15a_residential", D("1"),
                                  {"run_length_ft": 40, "access": "open"})]
    est = _estimate(healthy, library, pricebook, Province.ON, assemblies)
    result = run_audit(_ctx(est, assemblies, library, pricebook, min_margin="20"))
    assert "MARGIN_BELOW_MIN" not in codes(result)
    assert not result.blocks_pdf


def test_labor_cost_rate_clears_margin_flag(library, pricebook):
    # Billed $110/hr with a true loaded cost of $70/hr -> healthy labour margin,
    # so a normal job clears the 20% minimum without inflating the customer price.
    rates = ContractorRates(D("110"), D("70"), D("35"), D("0"), D("1"), labor_cost_rate_cad=D("70"))
    assemblies = [AssemblyRequest("circuit_new_15a_residential", D("1"),
                                  {"run_length_ft": 40, "access": "open"})]
    est = _estimate(rates, library, pricebook, Province.ON, assemblies)
    result = run_audit(_ctx(est, assemblies, library, pricebook, min_margin="20"))
    assert "MARGIN_BELOW_MIN" not in codes(result)
    assert not result.blocks_pdf


# --- individual rules -------------------------------------------------------

def test_permit_missing_on_service_change(library, pricebook, contractor):
    assemblies = [AssemblyRequest("service_upgrade_200a_overhead", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    flags = requires_permit_when_service_change(
        _ctx(est, assemblies, library, pricebook))
    assert flags and flags[0].code == "PERMIT_MISSING_SERVICE_CHANGE"


def test_permit_present_clears_flag(library, pricebook, contractor):
    permit = lookup_permit_fee(Province.ON, WorkCategory.SERVICE_CHANGE)
    extra = [CustomLineItem(permit.description_en, permit.description_fr, permit.fee_cad, "permit")]
    assemblies = [AssemblyRequest("service_upgrade_200a_overhead", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies, extra)
    assert requires_permit_when_service_change(_ctx(est, assemblies, library, pricebook)) == []


def test_afci_warning_for_new_circuit_ontario(library, pricebook, contractor):
    assemblies = [AssemblyRequest("circuit_new_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    flags = afci_required_for_new_circuits_in_dwelling(_ctx(est, assemblies, library, pricebook))
    assert flags and flags[0].code == "AFCI_MAY_BE_REQUIRED"


def test_travel_time_for_long_jobs(library, pricebook, contractor):
    assemblies = [AssemblyRequest("service_upgrade_200a_overhead", D("1"))]  # 8h
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    flags = travel_time_for_long_jobs(_ctx(est, assemblies, library, pricebook))
    assert flags and flags[0].severity == "info"


def test_hq_coordination_qc_service_change(library, pricebook, contractor):
    assemblies = [AssemblyRequest("service_upgrade_200a_overhead", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.QC, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook, province=Province.QC,
               customer_facing_scope="Upgrade to 200A service.")
    assert hq_coordination_for_qc_service_changes(ctx)
    # Mentioning Hydro-Québec clears it.
    ctx2 = _ctx(est, assemblies, library, pricebook, province=Province.QC,
                customer_facing_scope="Coordinate Hydro-Québec disconnect and reconnect.")
    assert hq_coordination_for_qc_service_changes(ctx2) == []


def test_scope_creep_language(library, pricebook, contractor):
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook,
               job_description="Add an outlet, and while you're at it check the panel.")
    flags = scope_creep_language_in_description(ctx)
    assert flags and flags[0].code == "SCOPE_CREEP_LANGUAGE"


def test_labor_hours_outside_band_detects_edit(library, pricebook, contractor):
    assemblies = [AssemblyRequest("circuit_new_15a_residential", D("1"),
                                  {"run_length_ft": 40, "access": "open"})]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    line = next(li for li in est.line_items if li.assembly_id == "circuit_new_15a_residential")
    # Engine-expected is 1.5h; pretend the contractor edited it down to 0.5h.
    ctx = _ctx(est, assemblies, library, pricebook,
               line_hours_override={line.line_number: D("0.5")})
    flags = labor_hours_outside_band_per_assembly(ctx)
    assert flags and flags[0].code == "LABOR_HOURS_OUTSIDE_BAND"


def test_labor_hours_in_band_no_flag(library, pricebook, contractor):
    assemblies = [AssemblyRequest("circuit_new_15a_residential", D("1"),
                                  {"run_length_ft": 40, "access": "open"})]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    assert labor_hours_outside_band_per_assembly(
        _ctx(est, assemblies, library, pricebook)) == []


def test_qc_customer_language_check(library, pricebook, contractor):
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.QC, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook, province=Province.QC,
               customer_province=Province.QC, customer_language="en")
    assert qc_customer_language_check(ctx)
    ctx_fr = _ctx(est, assemblies, library, pricebook, province=Province.QC,
                  customer_province=Province.QC, customer_language="fr")
    assert qc_customer_language_check(ctx_fr) == []


def test_qc_code_transition_warning(library, pricebook, contractor):
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.QC, assemblies)
    inside = _ctx(est, assemblies, library, pricebook, province=Province.QC,
                  permit_date=date(2026, 6, 1))
    assert qc_code_edition_transition_warning(inside)
    outside = _ctx(est, assemblies, library, pricebook, province=Province.QC,
                   permit_date=date(2026, 11, 1))
    assert qc_code_edition_transition_warning(outside) == []


def test_stale_pricing_detected(library, pricebook, contractor):
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    # Far-future as_of makes every used SKU stale (>90 days).
    ctx = _ctx(est, assemblies, library, pricebook)
    ctx.as_of = date(2027, 1, 1)
    flags = stale_material_pricing(ctx)
    assert flags and flags[0].code == "STALE_PRICING"


def test_stale_pricing_fresh_no_flag(library, pricebook, contractor):
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook)
    ctx.as_of = date(2026, 5, 23)
    assert stale_material_pricing(ctx) == []


def test_margin_rule_unit(library, pricebook):
    underbid = ContractorRates(D("110"), D("70"), D("0"), D("0"), D("1"))
    assemblies = [AssemblyRequest("recep_duplex_15a_residential", D("1"))]
    est = _estimate(underbid, library, pricebook, Province.ON, assemblies)
    flags = margin_below_minimum(_ctx(est, assemblies, library, pricebook, min_margin="20"))
    assert flags and flags[0].blocks_pdf


# --- real-world estimating protection (§24.3) -------------------------------

def test_underground_work_flags_locate_and_excavation(contractor, library, pricebook):
    assemblies = [AssemblyRequest("conduit_run_pvc_buried_per_ft", D("40"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook)
    locate = utility_locate_required(ctx)
    assert locate and locate[0].code == "UTILITY_LOCATE_REQUIRED" and not locate[0].blocks_pdf


def test_locate_warning_suppressed_when_scope_mentions_it(contractor, library, pricebook):
    assemblies = [AssemblyRequest("conduit_run_pvc_buried_per_ft", D("40"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook,
               customer_facing_scope="We will arrange utility locates before digging.")
    assert utility_locate_required(ctx) == []


def test_added_load_without_service_upgrade_flags_capacity(contractor, library, pricebook):
    assemblies = [AssemblyRequest("ev_charger_l2_attached_garage", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    flags = service_capacity_verification(_ctx(est, assemblies, library, pricebook))
    assert flags and flags[0].code == "SERVICE_CAPACITY_VERIFY"
    # A service upgrade in the same quote clears it (capacity is being addressed).
    upgraded = assemblies + [AssemblyRequest("service_upgrade_200a_overhead", D("1"))]
    est2 = _estimate(contractor, library, pricebook, Province.ON, upgraded)
    assert service_capacity_verification(_ctx(est2, upgraded, library, pricebook)) == []


def test_optional_addon_does_not_trigger_risk_rules(contractor, library, pricebook):
    # An optional EV charger must not raise a service-capacity warning (§24.4 + §24.3).
    assemblies = [
        AssemblyRequest("recep_duplex_15a_residential", D("1")),
        AssemblyRequest("ev_charger_l2_attached_garage", D("1"), is_optional=True),
    ]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    assert service_capacity_verification(_ctx(est, assemblies, library, pricebook)) == []


def test_customer_supplied_equipment_flagged(contractor, library, pricebook):
    assemblies = [AssemblyRequest("light_fixture_install_new", D("1"))]
    est = _estimate(contractor, library, pricebook, Province.ON, assemblies)
    ctx = _ctx(est, assemblies, library, pricebook,
               job_description="Install the chandelier the customer supplied.")
    flags = customer_supplied_equipment_check(ctx)
    assert flags and flags[0].code == "CUSTOMER_SUPPLIED_EQUIPMENT" and flags[0].severity == "warn"
