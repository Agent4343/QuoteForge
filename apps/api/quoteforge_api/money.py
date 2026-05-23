"""Money helpers. All monetary math in QuoteForge uses Decimal, never float.

The estimating engine and tax engine are deterministic; rounding must be too.
We round to cents using ROUND_HALF_UP at the point a value becomes a
customer-visible amount (line totals, subtotals, taxes, grand total).
Intermediate accumulations stay at full Decimal precision.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0")


def D(value: object) -> Decimal:
    """Coerce a value to Decimal without going through binary float.

    Floats are stringified first so e.g. D(0.1) is exactly Decimal('0.1').
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)  # type: ignore[arg-type]


def money(value: object) -> Decimal:
    """Round a value to cents (2 dp, half-up)."""
    return D(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def pct(value: object) -> Decimal:
    """Round a percentage value to two decimal places."""
    return D(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
