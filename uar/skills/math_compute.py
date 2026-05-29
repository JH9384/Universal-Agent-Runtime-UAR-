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

import logging
import os
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package, skill_guard

# Circuit breaker for SymPy computations (handles timeouts and errors)
_math_cb = CircuitBreaker(
    "math_compute", failure_threshold=3, recovery_timeout=30.0
)

# Configuration
MATH_TIMEOUT = max(
    1.0,
    float(os.getenv("MATH_TIMEOUT_SECONDS", "30").strip() or "30"),
)
MAX_EXPRESSION_SIZE = max(
    1, int(os.getenv("MATH_MAX_EXPRESSION_SIZE", "10000").strip() or "10000")
)

logger = logging.getLogger(__name__)


def _with_timeout(fn, timeout: float) -> Dict[str, Any]:
    """Run callable with timeout using daemon thread.

    Uses ``threading.Thread`` with ``join(timeout)`` instead of
    ``signal.SIGALRM`` so the timeout works on any thread (e.g.
    inside a ``ThreadPoolExecutor``) and on Windows where SIGALRM
    does not exist.
    """
    import threading

    _result: Dict[str, Any] = {}
    _exc: Exception | None = None

    def _target() -> None:
        nonlocal _result, _exc
        try:
            _result = fn()
        except Exception as e:
            _exc = e

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return {"success": False, "error": "Computation timed out"}
    if _exc is not None:
        return {"success": False, "error": str(_exc)}
    return _result


def _safe_sympy_eval(expr: str, timeout: float) -> Dict[str, Any]:
    """Safely evaluate SymPy expression with timeout."""
    import sympy  # type: ignore

    def _do_eval():
        result = sympy.sympify(expr)
        return {
            "success": True,
            "result": str(result),
            "result_latex": sympy.latex(result),
            "result_type": str(type(result).__name__),
        }

    return _with_timeout(_do_eval, timeout)


def _solve_equation(
    expr: str, variable: str = "x", timeout: float = MATH_TIMEOUT
) -> Dict[str, Any]:
    """Solve equation for variable."""
    import sympy

    if "=" not in expr:
        return {
            "success": False,
            "error": "Equation must contain '=' (e.g., 'x**2 - 4 = 0')",
        }

    def _do_solve():
        x = sympy.Symbol(variable)
        lhs_str, rhs_str = expr.split("=", 1)
        lhs = sympy.sympify(lhs_str)
        rhs = sympy.sympify(rhs_str)
        eq = sympy.Eq(lhs, rhs)
        solutions = sympy.solve(eq, x)
        return {
            "success": True,
            "solutions": [str(sol) for sol in solutions],
            "solution_count": len(solutions),
            "variable": variable,
        }

    return _with_timeout(_do_solve, timeout)


def _differentiate(
    expr: str, variable: str = "x", timeout: float = MATH_TIMEOUT
) -> Dict[str, Any]:
    """Differentiate expression with respect to variable."""
    import sympy

    def _do_diff():
        x = sympy.Symbol(variable)
        f = sympy.sympify(expr)
        df = sympy.diff(f, x)
        return {
            "success": True,
            "derivative": str(df),
            "derivative_latex": sympy.latex(df),
            "variable": variable,
        }

    return _with_timeout(_do_diff, timeout)


def _integrate(
    expr: str, variable: str = "x", timeout: float = MATH_TIMEOUT
) -> Dict[str, Any]:
    """Integrate expression with respect to variable."""
    import sympy

    def _do_integrate():
        x = sympy.Symbol(variable)
        f = sympy.sympify(expr)
        integral = sympy.integrate(f, x)
        return {
            "success": True,
            "integral": str(integral),
            "integral_latex": sympy.latex(integral),
            "variable": variable,
        }

    return _with_timeout(_do_integrate, timeout)


def _simplify(expr: str, timeout: float = MATH_TIMEOUT) -> Dict[str, Any]:
    """Simplify mathematical expression."""
    import sympy

    def _do_simplify():
        f = sympy.sympify(expr)
        simplified = sympy.simplify(f)
        return {
            "success": True,
            "original": str(f),
            "simplified": str(simplified),
            "simplified_latex": sympy.latex(simplified),
        }

    return _with_timeout(_do_simplify, timeout)


@register_skill("math_compute")
@skill_guard("Math compute", status="failed")
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
    err = require_package("sympy")
    if err:
        return err

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
            "error": "Expression too large",
            "operation": operation,
        }

    # Execute operation with circuit breaker
    result = _math_cb.call(
        lambda: _execute_operation(operation, expression, variable)
    )

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
        "solve": lambda: _solve_equation(expression, variable, MATH_TIMEOUT),
        "simplify": lambda: _simplify(expression, MATH_TIMEOUT),
        "differentiate": lambda: _differentiate(
            expression, variable, MATH_TIMEOUT
        ),
        "integrate": lambda: _integrate(expression, variable, MATH_TIMEOUT),
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
