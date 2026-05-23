"""Load and index assemblies from version-controlled YAML (§7, §8).

Assemblies live as YAML under ``/data/assemblies`` and are loaded into memory at
startup. Validation is strict; a bad file raises at load time. The compact LLM
index excludes ``draft`` assemblies (§8: unreviewed assemblies are hidden from
the model).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from quoteforge_api.assemblies.schema import Assembly, Status
from quoteforge_api.config import get_settings


class AssemblyLoadError(RuntimeError):
    pass


class AssemblyLibrary:
    def __init__(self, assemblies: dict[str, Assembly]):
        self._by_id = assemblies

    def get(self, assembly_id: str) -> Assembly:
        try:
            return self._by_id[assembly_id]
        except KeyError as exc:
            raise KeyError(f"Unknown assembly id: {assembly_id!r}") from exc

    def __contains__(self, assembly_id: str) -> bool:
        return assembly_id in self._by_id

    def all(self) -> list[Assembly]:
        return list(self._by_id.values())

    def reviewed(self) -> list[Assembly]:
        return [a for a in self._by_id.values() if a.status == Status.REVIEWED]

    def llm_index(self, include_draft: bool = False) -> list[dict]:
        """Compact index for the Claude system prompt.

        Reviewed assemblies only by default (§8). ``include_draft`` is for dev/test
        so the LLM flow can be exercised before electrician review.
        """
        source = self.all() if include_draft else self.reviewed()
        return [
            {
                "id": a.id,
                "category": a.category.value,
                "names": {"en": a.names.en, "fr": a.names.fr},
                "description": {"en": a.description.en, "fr": a.description.fr},
                "status": a.status.value,
                "parameters": {
                    name: {
                        "type": p.type.value,
                        "sensitivity": p.sensitivity.value,
                        **({"values": p.values} if p.values else {}),
                    }
                    for name, p in a.parameters.items()
                },
            }
            for a in source
        ]

    def indexable(self, include_draft: bool = False) -> set[str]:
        """Assembly ids the LLM is allowed to reference."""
        source = self.all() if include_draft else self.reviewed()
        return {a.id for a in source}


def load_library(directory: Path | None = None) -> AssemblyLibrary:
    directory = directory or get_settings().assemblies_dir
    directory = Path(directory)
    if not directory.is_dir():
        raise AssemblyLoadError(f"assemblies directory not found: {directory}")

    assemblies: dict[str, Assembly] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            continue
        try:
            assembly = Assembly.model_validate(raw)
        except ValidationError as exc:
            raise AssemblyLoadError(f"invalid assembly {path.name}:\n{exc}") from exc
        if assembly.id != path.stem:
            raise AssemblyLoadError(
                f"{path.name}: assembly id {assembly.id!r} must match filename stem"
            )
        if assembly.id in assemblies:
            raise AssemblyLoadError(f"duplicate assembly id {assembly.id!r}")
        assemblies[assembly.id] = assembly

    return AssemblyLibrary(assemblies)


@lru_cache
def get_library() -> AssemblyLibrary:
    return load_library()
