"""Shared test fixtures."""

from decimal import Decimal

import pytest

from quoteforge_api.assemblies.loader import load_library
from quoteforge_api.pricebook import load_pricebook
from quoteforge_api.services.estimating import ContractorRates


@pytest.fixture(scope="session")
def library():
    return load_library()


@pytest.fixture(scope="session")
def pricebook():
    return load_pricebook()


@pytest.fixture
def contractor() -> ContractorRates:
    """Reference contractor: $110/hr blended, 35% material markup, no labour
    markup, 1 hr minimum call-out, 20% minimum margin."""
    return ContractorRates(
        blended_labor_rate_cad=Decimal("110"),
        apprentice_labor_rate_cad=Decimal("70"),
        default_material_markup_pct=Decimal("35"),
        default_labor_markup_pct=Decimal("0"),
        minimum_callout_hours=Decimal("1"),
    )
