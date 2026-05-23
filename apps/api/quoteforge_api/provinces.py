"""Province is a first-class dimension (architectural principle §3.3).

Every assembly, tax calculation, permit lookup, and PDF template knows the
province. There is no "default Canada" mode.
"""

from __future__ import annotations

from enum import StrEnum


class Province(StrEnum):
    ON = "ON"
    QC = "QC"
    BC = "BC"
    AB = "AB"
    MB = "MB"
    SK = "SK"
    NS = "NS"
    NB = "NB"
    NL = "NL"
    PE = "PE"


PROVINCE_NAMES: dict[Province, dict[str, str]] = {
    Province.ON: {"en": "Ontario", "fr": "Ontario"},
    Province.QC: {"en": "Quebec", "fr": "Québec"},
    Province.BC: {"en": "British Columbia", "fr": "Colombie-Britannique"},
    Province.AB: {"en": "Alberta", "fr": "Alberta"},
    Province.MB: {"en": "Manitoba", "fr": "Manitoba"},
    Province.SK: {"en": "Saskatchewan", "fr": "Saskatchewan"},
    Province.NS: {"en": "Nova Scotia", "fr": "Nouvelle-Écosse"},
    Province.NB: {"en": "New Brunswick", "fr": "Nouveau-Brunswick"},
    Province.NL: {"en": "Newfoundland and Labrador", "fr": "Terre-Neuve-et-Labrador"},
    Province.PE: {"en": "Prince Edward Island", "fr": "Île-du-Prince-Édouard"},
}

# Provinces with a fully built assembly/tax/permit dataset at launch (§4).
LAUNCH_PROVINCES: frozenset[Province] = frozenset({Province.ON, Province.QC})
