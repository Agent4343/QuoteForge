"""Derived assembly confidence (§24.6).

Confidence is COMPUTED from review metadata, never hand-set, so it can't drift
from reality. Until an electrician reviews an assembly it is "unreviewed" — which
is the honest state of the whole library today (every assembly is status: draft).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from quoteforge_api.assemblies.schema import Assembly, Status

# A reviewed assembly that hasn't been re-validated within this window decays a
# confidence level (prices and code change; a year-old sign-off is not "high").
_STALE_DAYS = 365


class Confidence(StrEnum):
    UNREVIEWED = "unreviewed"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


def _parse(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def assembly_confidence(assembly: Assembly, as_of: date | None = None) -> Confidence:
    """Deterministic confidence for an assembly from its review metadata."""
    if assembly.status != Status.REVIEWED:
        return Confidence.UNREVIEWED
    as_of = as_of or date.today()
    last = _parse(assembly.last_field_validation) or _parse(assembly.last_reviewed)
    stale = last is None or (as_of - last).days > _STALE_DAYS
    if assembly.review_count >= 2 and assembly.provinces_reviewed and not stale:
        return Confidence.HIGH
    if assembly.review_count >= 1 and not stale:
        return Confidence.MODERATE
    return Confidence.LOW
