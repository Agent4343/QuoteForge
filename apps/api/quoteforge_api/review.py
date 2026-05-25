"""Electrician-review status reporting (§8, §21, §24.6).

Reads the version-controlled data (assemblies, price book, code matrix, permit
table) and reports what still needs a licensed electrician's sign-off before
launch. Pure reads — no database. Used by ``scripts/review_status.py``.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date

import yaml

from quoteforge_api.assemblies.confidence import assembly_confidence
from quoteforge_api.assemblies.loader import get_library
from quoteforge_api.assemblies.schema import Status
from quoteforge_api.config import get_settings
from quoteforge_api.pricebook import get_pricebook
from quoteforge_api.provinces import Province
from quoteforge_api.services.estimating import permits

# Columns a reviewer fills in on the worksheet (left blank by the generator).
_REVIEWER_COLUMNS = [
    "hours_ok", "materials_ok", "code_refs_ok", "reviewer", "review_date", "notes",
]


def assembly_rows(as_of: date | None = None) -> list[dict]:
    """One row per assembly listing the fields an electrician must confirm."""
    lib = get_library()
    rows: list[dict] = []
    for a in sorted(lib.all(), key=lambda x: x.id):
        rows.append({
            "id": a.id,
            "category": a.category.value,
            "status": a.status.value,
            "confidence": assembly_confidence(a, as_of).value,
            "customer_risk": a.customer_risk.value,
            "base_hours": str(a.labor.base_hours),
            "param_count": len(a.parameters),
            "material_skus": len(a.materials),
            "provinces_with_variant": ",".join(sorted(p.value for p in a.provincial_variants)),
            "code_refs": sum(len(v.code_refs) for v in a.provincial_variants.values()),
            "review_count": a.review_count,
            "provinces_reviewed": ",".join(p.value for p in a.provinces_reviewed),
            "last_reviewed": a.last_reviewed or "",
            "last_field_validation": a.last_field_validation or "",
        })
    return rows


def pricebook_status(as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    pb = get_pricebook()
    raw = json.loads(get_settings().pricebook_path.read_text(encoding="utf-8"))
    stale = sorted(pb.stale_skus(as_of))
    return {
        "total": len(pb.all_skus()),
        "stale": len(stale),
        "stale_skus": stale,
        "stale_after_days": pb.stale_after_days,
        "translation_status": raw.get("translation_status", "unknown"),
    }


def code_matrix_status() -> dict:
    path = get_settings().data_dir / "code_editions.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {"status": raw.get("status", "unknown"), "provinces": len(raw.get("provinces", {}))}


def permit_status(as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    entries = sum(
        1 for p in Province for wc in permits.WorkCategory if permits.lookup_permit_fee(p, wc)
    )
    return {
        "effective_date": permits.PERMIT_TABLE_EFFECTIVE_DATE.isoformat(),
        "review_by": permits.PERMIT_TABLE_REVIEW_BY.isoformat(),
        "review_due": as_of >= permits.PERMIT_TABLE_REVIEW_BY,
        "entries": entries,
    }


def summary(as_of: date | None = None) -> dict:
    rows = assembly_rows(as_of)
    by_confidence: dict[str, int] = {}
    reviewed = 0
    for r in rows:
        by_confidence[r["confidence"]] = by_confidence.get(r["confidence"], 0) + 1
        if r["status"] == Status.REVIEWED.value:
            reviewed += 1
    return {
        "assemblies": {
            "total": len(rows),
            "reviewed": reviewed,
            "draft": len(rows) - reviewed,
            "by_confidence": by_confidence,
        },
        "pricebook": pricebook_status(as_of),
        "code_matrix": code_matrix_status(),
        "permits": permit_status(as_of),
    }


def worksheet_csv(as_of: date | None = None) -> str:
    rows = assembly_rows(as_of)
    fields = list(rows[0].keys()) if rows else []
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields + _REVIEWER_COLUMNS)
    writer.writeheader()
    blanks = {c: "" for c in _REVIEWER_COLUMNS}
    for r in rows:
        writer.writerow({**r, **blanks})
    return buf.getvalue()


def format_summary(s: dict) -> str:
    a = s["assemblies"]
    pb = s["pricebook"]
    cm = s["code_matrix"]
    pm = s["permits"]
    conf = ", ".join(f"{k}={v}" for k, v in sorted(a["by_confidence"].items()))
    lines = [
        "QuoteForge — electrician review status (§8 / §21 / §24.6)",
        "=" * 58,
        f"Assemblies:  {a['reviewed']}/{a['total']} reviewed  ({a['draft']} draft)",
        f"  confidence: {conf}",
        f"Price book:  {pb['total']} SKUs, {pb['stale']} stale (>{pb['stale_after_days']}d), "
        f"FR translation_status={pb['translation_status']}",
        f"Code matrix: status={cm['status']}, {cm['provinces']} provinces",
        f"Permit fees: {pm['entries']} entries, effective {pm['effective_date']}, "
        f"review_by {pm['review_by']}" + ("  [REVIEW DUE]" if pm["review_due"] else ""),
        "",
        "To launch (§21): an electrician must verify each assembly's labour hours,",
        "material BOM, and per-province code_refs; confirm real supplier costs in the",
        "price book; verify permit fees; then set status: reviewed + the §24.6",
        "confidence fields. Run with --worksheet for a per-assembly checklist.",
    ]
    if pb["stale_skus"]:
        lines.append("Stale SKUs: " + ", ".join(pb["stale_skus"]))
    return "\n".join(lines)
