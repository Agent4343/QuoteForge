"""Tax engine tests (§11). Expected values hand-computed from the rate table."""

from decimal import Decimal

import pytest

from quoteforge_api.provinces import Province
from quoteforge_api.services.tax import compute_taxes


def D(s: str) -> Decimal:
    return Decimal(s)


def test_ontario_hst_on_materials_and_labour():
    # HST 13% on (1000 + 500) = 195.00; GST slot is 0.
    tb = compute_taxes(Province.ON, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("0.00")
    assert tb.pst_qst_hst_cad == D("195.00")
    assert tb.pst_qst_hst_label_en == "HST"
    assert tb.total_tax_cad == D("195.00")


def test_quebec_gst_and_qst_not_stacked():
    # GST 5% on 1500 = 75.00; QST 9.975% on 1500 = 149.625 -> 149.63 (not stacked).
    tb = compute_taxes(Province.QC, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("75.00")
    assert tb.pst_qst_hst_cad == D("149.63")
    assert tb.pst_qst_hst_label_en == "QST"
    assert tb.total_tax_cad == D("224.63")


def test_bc_pst_on_materials_only():
    # GST 5% on 1500 = 75.00; PST 7% on materials (1000) only = 70.00.
    tb = compute_taxes(Province.BC, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("75.00")
    assert tb.pst_qst_hst_cad == D("70.00")
    assert tb.total_tax_cad == D("145.00")


def test_alberta_gst_only():
    tb = compute_taxes(Province.AB, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("75.00")
    assert tb.pst_qst_hst_cad == D("0.00")
    assert tb.total_tax_cad == D("75.00")


def test_saskatchewan_pst6_materials_only():
    # GST 5% on 1500 = 75.00; PST 6% on materials (1000) = 60.00.
    tb = compute_taxes(Province.SK, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("75.00")
    assert tb.pst_qst_hst_cad == D("60.00")


def test_manitoba_rst7_materials_only():
    tb = compute_taxes(Province.MB, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("75.00")
    assert tb.pst_qst_hst_cad == D("70.00")
    assert tb.pst_qst_hst_label_en == "RST"


@pytest.mark.parametrize("prov", [Province.NS, Province.NB, Province.NL, Province.PE])
def test_atlantic_hst15(prov):
    # HST 15% on (1000 + 500) = 225.00.
    tb = compute_taxes(prov, D("1000.00"), D("500.00"))
    assert tb.gst_cad == D("0.00")
    assert tb.pst_qst_hst_cad == D("225.00")
    assert tb.total_tax_cad == D("225.00")


def test_rounding_half_up_to_cents():
    # QST 9.975% on 100.10 = 9.9849... -> 9.98
    tb = compute_taxes(Province.QC, D("100.10"), D("0.00"))
    assert tb.pst_qst_hst_cad == D("9.98")


def test_zero_subtotals():
    tb = compute_taxes(Province.ON, D("0.00"), D("0.00"))
    assert tb.total_tax_cad == D("0.00")
