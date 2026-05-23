"""Audit engine (§10). Runs every rule and reports blocking status.

Critical flags block PDF generation until the contractor explicitly overrides
them (§3.5). The API layer persists flags and override decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from quoteforge_api.services.audit.rules import ALL_RULES
from quoteforge_api.services.audit.types import AuditContext, AuditFlag


@dataclass
class AuditResult:
    flags: list[AuditFlag]

    @property
    def critical(self) -> list[AuditFlag]:
        return [f for f in self.flags if f.severity == "critical"]

    @property
    def warnings(self) -> list[AuditFlag]:
        return [f for f in self.flags if f.severity == "warn"]

    @property
    def infos(self) -> list[AuditFlag]:
        return [f for f in self.flags if f.severity == "info"]

    @property
    def passed(self) -> bool:
        """An estimate 'passes' when nothing critical is outstanding."""
        return not self.critical

    @property
    def blocks_pdf(self) -> bool:
        return bool(self.critical)


def run_audit(ctx: AuditContext) -> AuditResult:
    flags: list[AuditFlag] = []
    for rule in ALL_RULES:
        flags.extend(rule(ctx))
    # Stable severity ordering: critical first, then warn, then info.
    order = {"critical": 0, "warn": 1, "info": 2}
    flags.sort(key=lambda f: order.get(f.severity, 99))
    return AuditResult(flags=flags)
