"""Per-province code matrix (§3.3, §3.4)."""

from datetime import date

from quoteforge_api.code_editions import load_code_matrix
from quoteforge_api.provinces import Province


def test_all_provinces_present():
    m = load_code_matrix()
    assert set(m.all()) == set(Province)


def test_ontario_edition_and_no_transition():
    m = load_code_matrix()
    assert m.edition_in_force(Province.ON, date(2026, 5, 1)) == "OESC 2024 (28th)"
    assert m.in_transition(Province.ON, date(2026, 5, 1)) is False
    assert m.customer_language(Province.ON) == "en"


def test_quebec_transition_window_drives_edition():
    m = load_code_matrix()
    current = "Chapitre V (CCÉ 2015 + modifications QC)"
    pending = "Chapitre V 2026 (CCÉ 2021 + modifications QC)"
    # Before the window -> current edition, not in transition.
    assert m.edition_in_force(Province.QC, date(2026, 1, 1)) == current
    assert m.in_transition(Province.QC, date(2026, 1, 1)) is False
    # Inside the grace window -> still defaults to current, flagged as transitional.
    assert m.edition_in_force(Province.QC, date(2026, 6, 1)) == current
    assert m.in_transition(Province.QC, date(2026, 6, 1)) is True
    # After the window -> pending edition is mandatory.
    assert m.edition_in_force(Province.QC, date(2026, 10, 1)) == pending
    assert m.in_transition(Province.QC, date(2026, 10, 1)) is False


def test_quebec_defaults_to_french():
    assert load_code_matrix().customer_language(Province.QC) == "fr"
