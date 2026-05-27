"""Mathematical computation skill using SymPy.

Provides symbolic mathematics, algebraic manipulation, calculus,
and numerical computation capabilities through SymPy integration.

Environment Variables:
    MATH_TIMEOUT_SECONDS    - Timeout for computations (default: 30)
    MATH_MAX_EXPRESSION_SIZE - Maximum expression complexity (default: 10000)

Goal Metadata:
    math_operation - Operation type: 'solve', 'simplify',
                    'differentiate', 'integrate', 'evaluate'
    math_expression - Mathematical expression (string or SymPy format)
    math_variable - Variable for operations (e.g., 'x', 'y')
    math_domain - Optional domain specification (e.g., 'real', 'complex')
"""

import os
import logging
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)

# Circuit breaker for SymPy computations (handles timeouts and errors)
_math_cb = CircuitBreaker(
    "math_compute", failure_threshold=3, recovery_timeout=30.0
)

# Configuration
MATH_TIMEOUT = float(os.getenv("MATH_TIMEOUT_SECONDS", "30"))
MAX_EXPRESSION_SIZE = int(os.getenv("MATH_MAX_EXPRESSION_SIZE", "10000"))


def _check_sympy_available() -> bool:
    """Check if SymPy is available with graceful degradation."""
    import importlib.util

    return importlib.util.find_spec("sympy") is not None


def _safe_sympy_eval(expr: str, timeout: float) -> Dict[str, Any]:
    """Safely evaluate SymPy expression with timeout.

    Uses ``threading.Thread`` with ``join(timeout)`` instead of
    ``signal.SIGALRM`` so the timeout works on any thread (e.g.
    inside a ``ThreadPoolExecutor``) and on Windows where SIGALRM
    does not exist.
    """
    import sympy  # type: ignore
    import threading

    _result: Dict[str, Any] = {}
    _exc: Exception | None = None

    def _target() -> None:
        nonlocal _result, _exc
        try:
            result = sympy.sympify(expr)
            _result = {
                "success": True,
                "result": str(result),
                "result_latex": sympy.latex(result),
                "result_type": str(type(result).__name__),
            }
        except Exception as e:
            _exc = e

    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return {"success": False, "error": "Computation timed out"}
    if _exc is not None:
        return {"success": False, "error": str(_exc)}
    return _result


def _solve_equation(expr: str, variable: str = "x") -> Dict[str, Any]:
    """Solve equation for variable."""
    import sympy

    try:
        x = sympy.Symbol(variable)
        lhs = sympy.sympify(expr.split("=")[0])
        rhs = sympy.sympify(expr.split("=")[1])
        eq = sympy.Eq(lhs, rhs)
        solutions = sympy.solve(eq, x)

        return {
            "success": True,
            "solutions": [str(sol) for sol in solutions],
            "solution_count": len(solutions),
            "variable": variable,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _differentiate(expr: str, variable: str = "x") -> Dict[str, Any]:
    """Differentiate expression with respect to variable."""
    import sympy

    try:
        x = sympy.Symbol(variable)
        f = sympy.sympify(expr)
        df = sympy.diff(f, x)

        return {
            "success": True,
            "derivative": str(df),
            "derivative_latex": sympy.latex(df),
            "variable": variable,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _integrate(expr: str, variable: str = "x") -> Dict[str, Any]:
    """Integrate expression with respect to variable."""
    import sympy

    try:
        x = sympy.Symbol(variable)
        f = sympy.sympify(expr)
        integral = sympy.integrate(f, x)

        return {
            "success": True,
            "integral": str(integral),
            "integral_latex": sympy.latex(integral),
            "variable": variable,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _simplify(expr: str) -> Dict[str, Any]:
    """Simplify mathematical expression."""
    import sympy

    try:
        f = sympy.sympify(expr)
        simplified = sympy.simplify(f)

        return {
            "success": True,
            "original": str(f),
            "simplified": str(simplified),
            "simplified_latex": sympy.latex(simplified),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@register_skill("math_compute")
def math_compute(ctx: PipelineContext) -> Dict[str, Any]:
    """Perform mathematical computations using SymPy.

    Supports symbolic mathematics, algebraic manipulation, calculus,
    and numerical evaluation. Operations include solving equations,
    differentiation, integration, simplification, and evaluation.

    Environment:
        MATH_TIMEOUT_SECONDS - Timeout for computations (default: 30)
        MATH_MAX_EXPRESSION_SIZE - Max expression complexity (default: 10000)

    Goal metadata:
        math_operation - Operation: 'solve', 'simplify',
                        'differentiate', 'integrate', 'evaluate'
        math_expression - Mathematical expression (string)
        math_variable - Variable for operations (default: 'x')
        math_domain - Optional domain (default: 'real')

    Returns:
        Dictionary with computation results or error information.
    """
    # Check SymPy availability
    if not _check_sympy_available():
        return {
            "status": "failed",
            "error": "SymPy not installed. Install with: pip install sympy",
            "operation": "unavailable",
        }

    # Get parameters from goal metadata
    operation = ctx.goal.metadata.get("math_operation", "evaluate")
    expression = ctx.goal.metadata.get("math_expression", "")
    variable = ctx.goal.metadata.get("math_variable", "x")

    # Validate inputs
    if not expression:
        return {
            "status": "failed",
            "error": "math_expression is required in goal metadata",
            "operation": operation,
        }

    if len(expression) > MAX_EXPRESSION_SIZE:
        return {
            "status": "failed",
            "error": f"Expression too large (max {MAX_EXPRESSION_SIZE} chars)",
            "operation": operation,
        }

    # Execute operation with circuit breaker
    try:
        result = _math_cb.call(
            lambda: _execute_operation(operation, expression, variable)
        )
    except Exception as exc:
        logger.warning(f"math_compute failed: {exc}")
        return {"status": "failed", "error": str(exc), "operation": operation}

    # Add metadata to result
    result["operation"] = operation
    result["expression"] = expression
    result["variable"] = variable
    result["status"] = "completed" if result.get("success") else "failed"

    return result


def _execute_operation(
    operation: str, expression: str, variable: str
) -> Dict[str, Any]:
    """Execute the specified mathematical operation."""
    operations = {
        "solve": lambda: _solve_equation(expression, variable),
        "simplify": lambda: _simplify(expression),
        "differentiate": lambda: _differentiate(expression, variable),
        "integrate": lambda: _integrate(expression, variable),
        "evaluate": lambda: _safe_sympy_eval(expression, MATH_TIMEOUT),
    }

    if operation not in operations:
        return {
            "success": False,
            "error": (
                f"Unknown operation: {operation}. "
                f"Available: {list(operations.keys())}"
            ),
        }

    return operations[operation]()
