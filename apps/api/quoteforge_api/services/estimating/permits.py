"""Permit fee lookup (§9 step 4).

Static lookup table keyed by (province, work_category). Fees are hardcoded and
carry a ``review_by`` date so they are revisited every six months (§9). These
are PLACEHOLDER fees pending verification against current ESA / RBQ / municipal
schedules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from quoteforge_api.money import D
from quoteforge_api.provinces import Province

PERMIT_TABLE_EFFECTIVE_DATE = date(2026, 5, 1)
PERMIT_TABLE_REVIEW_BY = date(2026, 11, 1)


class WorkCategory(StrEnum):
    SERVICE_CHANGE = "service_change"
    NEW_INSTALLATION = "new_installation"
    ALTERATION = "alteration"
    MINOR = "minor"


@dataclass(frozen=True)
class PermitFee:
    province: Province
    work_category: WorkCategory
    fee_cad: Decimal
    description_en: str
    description_fr: str
    effective_date: date
    review_by: date


# PLACEHOLDER fees (CAD). Verify against ESA (ON) / RBQ + municipal (QC) before launch.
_FEES: dict[tuple[Province, WorkCategory], tuple[Decimal, str, str]] = {
    (Province.ON, WorkCategory.SERVICE_CHANGE): (
        D("132.00"),
        "ESA notification — residential service change",
        "Avis ESA — changement de branchement résidentiel",
    ),
    (Province.ON, WorkCategory.NEW_INSTALLATION): (
        D("110.00"),
        "ESA notification — new installation",
        "Avis ESA — nouvelle installation",
    ),
    (Province.ON, WorkCategory.ALTERATION): (
        D("95.00"),
        "ESA notification — alteration",
        "Avis ESA — modification",
    ),
    (Province.ON, WorkCategory.MINOR): (
        D("95.00"),
        "ESA notification — minor work",
        "Avis ESA — travaux mineurs",
    ),
    (Province.QC, WorkCategory.SERVICE_CHANGE): (
        D("150.00"),
        "Municipal electrical permit — service change",
        "Permis d'électricité municipal — changement de branchement",
    ),
    (Province.QC, WorkCategory.NEW_INSTALLATION): (
        D("120.00"),
        "Municipal electrical permit — new installation",
        "Permis d'électricité municipal — nouvelle installation",
    ),
    (Province.QC, WorkCategory.ALTERATION): (
        D("100.00"),
        "Municipal electrical permit — alteration",
        "Permis d'électricité municipal — modification",
    ),
    (Province.QC, WorkCategory.MINOR): (
        D("100.00"),
        "Municipal electrical permit — minor work",
        "Permis d'électricité municipal — travaux mineurs",
    ),
}


def lookup_permit_fee(
    province: Province,
    work_category: WorkCategory,
    municipality: str | None = None,
    amperage: int | None = None,
) -> PermitFee | None:
    """Return the permit fee for a province + work category, or ``None`` if no
    fee is on file. ``municipality`` and ``amperage`` are accepted for forward
    compatibility but not yet used in the flat table."""
    entry = _FEES.get((province, work_category))
    if entry is None:
        return None
    fee, en, fr = entry
    return PermitFee(
        province=province,
        work_category=work_category,
        fee_cad=fee,
        description_en=en,
        description_fr=fr,
        effective_date=PERMIT_TABLE_EFFECTIVE_DATE,
        review_by=PERMIT_TABLE_REVIEW_BY,
    )
