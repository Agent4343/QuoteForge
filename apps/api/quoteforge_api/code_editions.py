"""Per-province electrical-code matrix (§3.3, §3.4).

A single version-controlled source of truth for each province's code edition,
regulator, permit model, utility, and any in-progress edition transition — so
this knowledge lives in one reviewed file instead of being sprinkled across the
49 assembly YAMLs. The estimating/quote layer and the audit read from here.

VERIFY the contents against official provincial sources before customer-facing
use (§3.6); see data/code_editions.yaml.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from quoteforge_api.config import get_settings
from quoteforge_api.provinces import Province


class Bilingual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    en: str
    fr: str

    def text(self, lang: str) -> str:
        return self.fr if lang == "fr" else self.en


class Edition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    base_cec: str | None = None
    effective_date: date | None = None


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date
    end: date


class ProvinceCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    regulator: Bilingual
    permit_model: Bilingual
    utility: str | None = None
    customer_language_default: str = "en"
    current_edition: Edition
    pending_edition: Edition | None = None
    transition: Transition | None = None


class CodeMatrix:
    def __init__(self, provinces: dict[Province, ProvinceCode]):
        self._by_prov = provinces

    def get(self, province: Province) -> ProvinceCode:
        return self._by_prov[province]

    def edition_in_force(self, province: Province, on_date: date | None) -> str:
        """The code-edition label in force on ``on_date`` (defaults to today).

        Once a province's transition window has ended (or the pending edition's
        effective date has passed with no window), the pending edition is the
        one in force; during the window the current edition is the default.
        """
        pc = self.get(province)
        when = on_date or date.today()
        if pc.pending_edition is not None:
            cutover = pc.transition.end if pc.transition else pc.pending_edition.effective_date
            if cutover is not None and when >= cutover:
                return pc.pending_edition.label
        return pc.current_edition.label

    def in_transition(self, province: Province, on_date: date | None) -> bool:
        pc = self.get(province)
        if pc.transition is None or on_date is None:
            return False
        return pc.transition.start <= on_date <= pc.transition.end

    def customer_language(self, province: Province) -> str:
        return self.get(province).customer_language_default

    def all(self) -> dict[Province, ProvinceCode]:
        return dict(self._by_prov)


def load_code_matrix(path: Path | None = None) -> CodeMatrix:
    path = Path(path or (get_settings().data_dir / "code_editions.yaml"))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    provinces: dict[Province, ProvinceCode] = {}
    for key, value in raw["provinces"].items():
        provinces[Province(key)] = ProvinceCode.model_validate(value)
    missing = set(Province) - set(provinces)
    if missing:
        raise RuntimeError(f"code_editions.yaml missing provinces: {sorted(p.value for p in missing)}")
    return CodeMatrix(provinces)


@lru_cache
def get_code_matrix() -> CodeMatrix:
    return load_code_matrix()
