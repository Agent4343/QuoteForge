"""Provincial tax engine (§11). Pure Python, table-driven, fully tested."""

from quoteforge_api.services.tax.engine import (
    TAX_TABLE_EFFECTIVE_DATE,
    TaxBreakdown,
    compute_taxes,
)

__all__ = ["TaxBreakdown", "compute_taxes", "TAX_TABLE_EFFECTIVE_DATE"]
