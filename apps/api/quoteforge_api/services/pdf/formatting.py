"""Locale-aware formatting for CAD quotes (§14, §17).

en-CA: $1,234.56 / "May 23, 2026"
fr-CA: 1 234,56 $ / "23 mai 2026" (non-breaking spaces, comma decimal, $ after)

Implemented without an i18n library to keep the dependency surface small; the
output matches the CAD conventions the PDFs need.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

NBSP = " "

_FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_EN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _group_thousands(integer_part: str, sep: str) -> str:
    digits = integer_part.lstrip("-")
    sign = "-" if integer_part.startswith("-") else ""
    out = ""
    while len(digits) > 3:
        out = sep + digits[-3:] + out
        digits = digits[:-3]
    return sign + digits + out


def format_currency(amount: Decimal | None, lang: str) -> str:
    value = Decimal(amount or 0).quantize(Decimal("0.01"))
    sign = "-" if value < 0 else ""
    whole, _, frac = f"{abs(value):.2f}".partition(".")
    if lang == "fr":
        grouped = _group_thousands(whole, NBSP)
        return f"{sign}{grouped},{frac}{NBSP}$"
    grouped = _group_thousands(whole, ",")
    return f"{sign}${grouped}.{frac}"


def format_pct(rate: Decimal, lang: str) -> str:
    # rate is a fraction (0.13 -> 13). Trim trailing zeros (0.09975 -> 9.975).
    pct = (Decimal(rate) * 100).normalize()
    text = format(pct, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if lang == "fr":
        return f"{text.replace('.', ',')}{NBSP}%"
    return f"{text}%"


def format_date(d: date | None, lang: str) -> str:
    if d is None:
        return "—"
    if lang == "fr":
        return f"{d.day}{NBSP}{_FR_MONTHS[d.month - 1]}{NBSP}{d.year}"
    return f"{_EN_MONTHS[d.month - 1]} {d.day}, {d.year}"
