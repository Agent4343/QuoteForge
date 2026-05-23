"""Safe arithmetic evaluator for assembly ``qty_formula`` expressions.

We never ``eval`` untrusted-shaped strings. Formulas are parsed to an AST and
only a whitelist of arithmetic nodes and helper functions is permitted. All
math runs in Decimal so material quantities stay deterministic.

Supported: + - * / // % ** , parentheses, unary minus, numeric literals,
parameter names, and the helpers ceil, floor, round, min, max, abs.
"""

from __future__ import annotations

import ast
import math
from decimal import Decimal

from quoteforge_api.money import D


def _ceil(x: Decimal) -> Decimal:
    return Decimal(math.ceil(x))


def _floor(x: Decimal) -> Decimal:
    return Decimal(math.floor(x))


def _round(x: Decimal, ndigits: int = 0) -> Decimal:
    q = Decimal(1).scaleb(-int(ndigits))
    return D(x).quantize(q)


_FUNCS = {
    "ceil": _ceil,
    "floor": _floor,
    "round": _round,
    "min": lambda *a: min(a),
    "max": lambda *a: max(a),
    "abs": abs,
}

_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)


class FormulaError(ValueError):
    pass


def evaluate_formula(expr: str, params: dict[str, object]) -> Decimal:
    """Evaluate ``expr`` with ``params`` bound as Decimal-coerced names."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"invalid formula {expr!r}: {exc}") from exc

    env: dict[str, Decimal] = {}
    for k, v in params.items():
        if isinstance(v, bool) or v is None:
            continue
        try:
            env[k] = D(v)
        except (ArithmeticError, ValueError, TypeError):
            continue  # non-numeric params (e.g. enum strings) aren't usable in formulas

    def _eval(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise FormulaError(f"unsupported literal {node.value!r}")
            return D(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise FormulaError(f"unknown parameter {node.id!r} in formula {expr!r}")
            return D(env[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, _BINOPS):
            left, right = _eval(node.left), _eval(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.FloorDiv):
                return D(left // right)
            if isinstance(op, ast.Mod):
                return left % right
            if isinstance(op, ast.Pow):
                return left**right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = _eval(node.operand)
            return val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = _FUNCS.get(node.func.id)
            if fn is None:
                raise FormulaError(f"unknown function {node.func.id!r}")
            args = [_eval(a) for a in node.args]
            return D(fn(*args))
        raise FormulaError(f"unsupported expression element: {ast.dump(node)}")

    return _eval(tree)
