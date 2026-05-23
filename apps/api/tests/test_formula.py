"""Safe formula evaluator tests."""

from decimal import Decimal

import pytest

from quoteforge_api.services.estimating.formula import FormulaError, evaluate_formula


def test_basic_arithmetic():
    assert evaluate_formula("a + b * 2", {"a": 3, "b": 4}) == Decimal("11")


def test_ceil_floor_round():
    assert evaluate_formula("ceil(run / 4)", {"run": 15}) == Decimal("4")
    assert evaluate_formula("floor(run / 4)", {"run": 15}) == Decimal("3")
    assert evaluate_formula("round(x, 1)", {"x": Decimal("2.345")}) == Decimal("2.3")


def test_min_max_abs():
    assert evaluate_formula("max(a, b)", {"a": 2, "b": 9}) == Decimal("9")
    assert evaluate_formula("min(a, b)", {"a": 2, "b": 9}) == Decimal("2")
    assert evaluate_formula("abs(-x)", {"x": 5}) == Decimal("5")


def test_unknown_parameter_raises():
    with pytest.raises(FormulaError):
        evaluate_formula("a + missing", {"a": 1})


def test_unknown_function_raises():
    with pytest.raises(FormulaError):
        evaluate_formula("danger(1)", {})


def test_no_attribute_access_or_calls_into_objects():
    with pytest.raises(FormulaError):
        evaluate_formula("a.__class__", {"a": 1})


def test_no_arbitrary_names():
    with pytest.raises(FormulaError):
        evaluate_formula("__import__", {})
