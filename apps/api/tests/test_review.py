"""Electrician-review status reporting (§8/§21/§24.6)."""

from __future__ import annotations

from quoteforge_api.review import assembly_rows, format_summary, summary, worksheet_csv


def test_summary_reflects_unreviewed_library():
    s = summary()
    a = s["assemblies"]
    # Whole library is draft today -> nothing reviewed, all unreviewed confidence.
    assert a["total"] == a["draft"] > 0
    assert a["reviewed"] == 0
    assert a["by_confidence"].get("unreviewed") == a["total"]
    assert s["pricebook"]["total"] > 0
    assert s["pricebook"]["translation_status"] == "draft"
    assert s["code_matrix"]["status"] == "draft"
    assert s["code_matrix"]["provinces"] == 10
    assert s["permits"]["entries"] > 0


def test_worksheet_has_one_row_per_assembly_plus_reviewer_columns():
    rows = assembly_rows()
    csv_text = worksheet_csv()
    lines = csv_text.splitlines()
    assert len(lines) == len(rows) + 1  # header + one row per assembly
    header = lines[0]
    for col in ("id", "base_hours", "code_refs", "reviewer", "review_date", "notes"):
        assert col in header
    assert any("circuit_new_15a_residential" in line for line in lines[1:])


def test_format_summary_is_human_readable():
    text = format_summary(summary())
    assert "electrician review status" in text
    assert "Assemblies:" in text and "Price book:" in text
