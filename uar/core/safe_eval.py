"""Restricted AST-based expression evaluator for safe math evaluation.

Replaces raw ``eval()`` in skill code to prevent sandbox escapes while
still supporting the arithmetic, NumPy functions, and subscripting that
skills require.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, Optional

# Whitelist of AST node types that may appear in a safe expression.
_ALLOWED_NODES = frozenset(
    {
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Index,  # Python < 3.9 compatibility
        ast.Slice,
        ast.ExtSlice,
        ast.Call,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Compare,
        ast.BoolOp,
        ast.IfExp,
        ast.JoinedStr,
        ast.FormattedValue,
        ast.keyword,
        # Operators
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Invert,
        ast.BitOr,
        ast.BitXor,
        ast.BitAnd,
        ast.LShift,
        ast.RShift,
        ast.Load,
        # Starred may appear inside list/tuple literals; harmless.
        ast.Starred,
    }
)

# Dunder attributes that must never be accessed.
_DISALLOWED_ATTRS = frozenset(
    {
        "__class__",
        "__mro__",
        "__bases__",
        "__subclasses__",
        "__globals__",
        "__builtins__",
        "__import__",
        "__code__",
        "__func__",
        "__self__",
        "__module__",
        "__dict__",
        "__weakref__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__get__",
        "__set__",
        "__delete__",
    }
)


class SafeEvalError(Exception):
    """Raised when an expression contains disallowed constructs."""


class SafeEvalNodeError(SafeEvalError):
    """Raised when a disallowed AST node is encountered."""


class SafeEvalNameError(SafeEvalError):
    """Raised when a disallowed name is referenced."""


class SafeEvalAttrError(SafeEvalError):
    """Raised when a disallowed attribute is accessed."""


def _validate_node(node: ast.AST) -> None:
    """Recursively validate that *node* is in the allow-list."""
    if type(node) not in _ALLOWED_NODES:
        raise SafeEvalNodeError(
            f"Disallowed AST node: {type(node).__name__}"
        )
    for child in ast.iter_child_nodes(node):
        _validate_node(child)


def _validate_names(tree: ast.AST, allowed_names: set[str]) -> None:
    """Ensure every ``ast.Name`` in *tree* is in *allowed_names*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise SafeEvalNameError(
                    f"Disallowed name: {node.id}"
                )
        elif isinstance(node, ast.Attribute):
            if node.attr in _DISALLOWED_ATTRS:
                raise SafeEvalAttrError(
                    f"Disallowed attribute access: {node.attr}"
                )


def _safe_eval(
    tree: ast.Expression,
    namespace: Dict[str, Any],
) -> Any:
    """Evaluate a validated AST *tree* with a restricted namespace."""
    code = compile(tree, "<safe_eval>", "eval")
    return eval(code, {"__builtins__": {}}, namespace)  # noqa: S307


def safe_eval(
    expr: str,
    namespace: Optional[Dict[str, Any]] = None,
    *,
    max_len: int = 4096,
) -> Any:
    """Safely evaluate a mathematical expression string.

    Args:
        expr: Expression string (e.g. ``"x[0]**2 + np.sin(x[1])"``).
        namespace: Mapping of allowed names to values (e.g.
            ``{"np": np, "x": x, "sin": np.sin}``).
        max_len: Maximum allowed length of *expr* to prevent DoS via
            deeply nested ASTs.

    Returns:
        Result of the evaluated expression.

    Raises:
        SafeEvalError: If the expression contains disallowed constructs.
        SyntaxError: If *expr* is not valid Python syntax.
    """
    if len(expr) > max_len:
        raise SafeEvalError(
            f"Expression too long: {len(expr)} > {max_len}"
        )

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise SafeEvalError(f"Invalid expression syntax: {exc}") from exc

    _validate_node(tree)
    _validate_names(
        tree, allowed_names=set(namespace.keys()) if namespace else set()
    )

    return _safe_eval(tree, namespace or {})


def safe_eval_with_numpy(
    expr: str,
    local_vars: Optional[Dict[str, Any]] = None,
    *,
    max_len: int = 4096,
) -> Any:
    """Convenience wrapper that auto-injects common NumPy/math helpers.

    Injects ``np`` (numpy), ``sin``, ``cos``, ``exp``, ``log``,
    ``pi``, ``e``, and ``inf`` if numpy is available.
    """
    ns: Dict[str, Any] = dict(local_vars) if local_vars else {}

    import numpy as np

    ns.setdefault("np", np)
    ns.setdefault("sin", np.sin)
    ns.setdefault("cos", np.cos)
    ns.setdefault("exp", np.exp)
    ns.setdefault("log", np.log)
    ns.setdefault("pi", np.pi)
    ns.setdefault("e", np.e)
    ns.setdefault("inf", np.inf)

    return safe_eval(expr, ns, max_len=max_len)
