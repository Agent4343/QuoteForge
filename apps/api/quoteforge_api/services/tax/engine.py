"""Provincial sales tax rules (§11).

Rules as of 2026-05. The table carries an effective date so updates are
auditable. A single ``compute_taxes`` function is the only entry point.

Model (matches the Quote schema fields ``tax_gst_cad`` and
``tax_pst_qst_hst_cad``):

* GST/HST provinces (ON, NS, NB, NL, PE): the combined HST is reported in the
  provincial slot; the federal-only GST slot is zero.
* GST + provincial-tax provinces (QC, BC, AB, SK, MB): the 5% GST is reported
  in the GST slot; the provincial portion (QST/PST/RST) in the provincial slot.

Tax base differences:
* HST and GST apply to materials + labour.
* QST applies to materials + labour, computed on the pre-GST amount (Quebec
  de-harmonised the QST base in 2013, so it is *not* stacked on top of GST).
* BC PST (7%), SK PST (6%), MB RST (7%) apply to materials only; labour is
  treated as exempt for the electrical work categories in scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from quoteforge_api.money import ZERO, D, money
from quoteforge_api.provinces import Province

TAX_TABLE_EFFECTIVE_DATE = date(2026, 5, 1)


@dataclass(frozen=True)
class _Rule:
    gst_rate: Decimal  # federal GST portion reported separately (0 for HST provinces)
    prov_rate: Decimal  # HST / QST / PST / RST rate
    prov_label_en: str  # "HST" | "QST" | "PST" | "RST"
    prov_label_fr: str  # "TVH" | "TVQ" | "TVP" | "TVD"
    prov_on_labour: bool  # whether the provincial tax applies to labour
    # gst_on_labour is always True where gst_rate > 0 for the categories in scope.


# Decimal rates expressed as fractions.
_RULES: dict[Province, _Rule] = {
    Province.ON: _Rule(ZERO, D("0.13"), "HST", "TVH", prov_on_labour=True),
    Province.NS: _Rule(ZERO, D("0.15"), "HST", "TVH", prov_on_labour=True),
    Province.NB: _Rule(ZERO, D("0.15"), "HST", "TVH", prov_on_labour=True),
    Province.NL: _Rule(ZERO, D("0.15"), "HST", "TVH", prov_on_labour=True),
    Province.PE: _Rule(ZERO, D("0.15"), "HST", "TVH", prov_on_labour=True),
    Province.QC: _Rule(D("0.05"), D("0.09975"), "QST", "TVQ", prov_on_labour=True),
    Province.BC: _Rule(D("0.05"), D("0.07"), "PST", "TVP", prov_on_labour=False),
    Province.SK: _Rule(D("0.05"), D("0.06"), "PST", "TVP", prov_on_labour=False),
    Province.MB: _Rule(D("0.05"), D("0.07"), "RST", "TVD", prov_on_labour=False),
    Province.AB: _Rule(D("0.05"), ZERO, "", "", prov_on_labour=False),
}


@dataclass(frozen=True)
class TaxBreakdown:
    """Result of a tax computation. All amounts rounded to cents."""

    province: Province
    gst_cad: Decimal
    gst_rate: Decimal
    pst_qst_hst_cad: Decimal
    pst_qst_hst_rate: Decimal
    pst_qst_hst_label_en: str
    pst_qst_hst_label_fr: str
    total_tax_cad: Decimal
    effective_date: date


def compute_taxes(
    province: Province,
    materials_subtotal: Decimal,
    labor_subtotal: Decimal,
) -> TaxBreakdown:
    """Compute the tax breakdown for a province given priced subtotals.

    ``materials_subtotal`` and ``labor_subtotal`` are the customer-facing
    (already marked-up) amounts the tax applies to.
    """
    rule = _RULES[province]
    materials = D(materials_subtotal)
    labor = D(labor_subtotal)

    gst_base = materials + labor if rule.gst_rate > ZERO else ZERO
    gst = money(gst_base * rule.gst_rate)

    prov_base = materials + (labor if rule.prov_on_labour else ZERO)
    prov = money(prov_base * rule.prov_rate)

    return TaxBreakdown(
        province=province,
        gst_cad=gst,
        gst_rate=rule.gst_rate,
        pst_qst_hst_cad=prov,
        pst_qst_hst_rate=rule.prov_rate,
        pst_qst_hst_label_en=rule.prov_label_en,
        pst_qst_hst_label_fr=rule.prov_label_fr,
        total_tax_cad=money(gst + prov),
        effective_date=TAX_TABLE_EFFECTIVE_DATE,
    )
