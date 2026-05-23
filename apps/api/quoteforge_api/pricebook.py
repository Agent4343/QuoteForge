"""Material price book (§9 step 1).

A flat JSON catalogue of SKUs loaded into memory. Provides cost lookup and
staleness detection (anything older than ``stale_after_days`` is flagged by the
audit engine, never silently used as fresh).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from quoteforge_api.config import get_settings
from quoteforge_api.money import D


@dataclass(frozen=True)
class Material:
    sku: str
    description_en: str
    description_fr: str
    unit: str
    cost_cad: Decimal
    supplier: str
    last_updated: date

    def is_stale(self, as_of: date, stale_after_days: int) -> bool:
        return (as_of - self.last_updated).days > stale_after_days


class PriceBook:
    def __init__(self, materials: dict[str, Material], stale_after_days: int):
        self._materials = materials
        self.stale_after_days = stale_after_days

    def get(self, sku: str) -> Material:
        try:
            return self._materials[sku]
        except KeyError as exc:
            raise KeyError(f"Unknown material SKU: {sku!r}") from exc

    def __contains__(self, sku: str) -> bool:
        return sku in self._materials

    def all_skus(self) -> list[str]:
        return list(self._materials)

    def stale_skus(self, as_of: date) -> list[str]:
        return [
            sku
            for sku, m in self._materials.items()
            if m.is_stale(as_of, self.stale_after_days)
        ]


def load_pricebook(path: Path | None = None) -> PriceBook:
    path = path or get_settings().pricebook_path
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    stale_after = int(raw.get("stale_after_days", 90))
    materials: dict[str, Material] = {}
    for sku, m in raw["materials"].items():
        materials[sku] = Material(
            sku=sku,
            description_en=m["description_en"],
            description_fr=m["description_fr"],
            unit=m["unit"],
            cost_cad=D(m["cost_cad"]),
            supplier=m.get("supplier", raw.get("default_supplier", "")),
            last_updated=date.fromisoformat(m["last_updated"]),
        )
    return PriceBook(materials, stale_after)


@lru_cache
def get_pricebook() -> PriceBook:
    return load_pricebook()
