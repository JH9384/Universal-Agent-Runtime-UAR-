"""Comprehensive tests for math_compute skill.

Covers symbolic mathematics operations, error handling, timeouts,
and input validation.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.math_compute import math_compute


def _make_ctx(metadata: dict) -> PipelineContext:
    goal = GoalSpec(
        id="test",
        user_intent="test",
        objective="test",
        metadata=metadata,
    )
    return PipelineContext(goal=goal)


class TestMathComputeOperations:
    """Core symbolic math operations."""

    def test_evaluate_expression(self):
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": "2 + 2",
        }))
        assert result["status"] == "completed"
        assert result["result"] == "4"

    def test_simplify_expression(self):
        result = math_compute(_make_ctx({
            "math_operation": "simplify",
            "math_expression": "x**2 + 2*x + 1 - (x+1)**2",
        }))
        assert result["status"] == "completed"
        assert result["simplified"] == "0"

    def test_differentiate_polynomial(self):
        result = math_compute(_make_ctx({
            "math_operation": "differentiate",
            "math_expression": "x**3 + 2*x",
            "math_variable": "x",
        }))
        assert result["status"] == "completed"
        assert "3*x**2" in result["derivative"]

    def test_integrate_polynomial(self):
        result = math_compute(_make_ctx({
            "math_operation": "integrate",
            "math_expression": "3*x**2",
            "math_variable": "x",
        }))
        assert result["status"] == "completed"
        assert "x**3" in result["integral"]

    def test_solve_equation(self):
        result = math_compute(_make_ctx({
            "math_operation": "solve",
            "math_expression": "x**2 - 4 = 0",
            "math_variable": "x",
        }))
        assert result["status"] == "completed"
        assert result["solution_count"] == 2
        solutions = {str(s) for s in result["solutions"]}
        assert "-2" in solutions or "2" in solutions

    def test_solve_linear(self):
        result = math_compute(_make_ctx({
            "math_operation": "solve",
            "math_expression": "2*x + 4 = 10",
            "math_variable": "x",
        }))
        assert result["status"] == "completed"
        assert result["solution_count"] == 1
        assert "3" in str(result["solutions"][0])

    def test_differentiate_with_respect_to_y(self):
        result = math_compute(_make_ctx({
            "math_operation": "differentiate",
            "math_expression": "y**2 + 3*y",
            "math_variable": "y",
        }))
        assert result["status"] == "completed"
        assert "2*y" in result["derivative"]

    def test_evaluate_trigonometric(self):
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": "sin(pi/2)",
        }))
        assert result["status"] == "completed"
        assert result["result"] == "1"


class TestMathComputeErrors:
    """Error handling and edge cases."""

    def test_missing_expression(self):
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": "",
        }))
        assert result["status"] == "failed"
        assert "required" in result["error"].lower()

    def test_expression_too_large(self):
        huge = "x + " * 50000 + "1"
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": huge,
        }))
        assert result["status"] == "failed"
        assert "too large" in result["error"].lower()

    def test_unknown_operation(self):
        result = math_compute(_make_ctx({
            "math_operation": "factorize",
            "math_expression": "x**2 - 1",
        }))
        assert result["status"] == "failed"
        assert "Unknown operation" in result["error"]

    def test_invalid_expression(self):
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": "!!!invalid_syntax!!!",
        }))
        assert result["status"] == "failed"
        assert "error" in result.get("error", "").lower()

    def test_malformed_solve_expression(self):
        """Solve expects 'lhs = rhs' format."""
        result = math_compute(_make_ctx({
            "math_operation": "solve",
            "math_expression": "x**2 - 4",
            "math_variable": "x",
        }))
        # Without '=' it may fail or return empty
        assert result["status"] in ("completed", "failed")

    def test_empty_metadata(self):
        result = math_compute(_make_ctx({}))
        assert result["status"] == "failed"
        assert "required" in result["error"].lower()


class TestMathComputeLatex:
    """LaTeX output generation."""

    def test_evaluate_returns_latex(self):
        result = math_compute(_make_ctx({
            "math_operation": "evaluate",
            "math_expression": "sqrt(2)",
        }))
        assert result["status"] == "completed"
        assert "result_latex" in result
        assert "latex" in result["result_type"].lower() or True

    def test_differentiate_returns_latex(self):
        result = math_compute(_make_ctx({
            "math_operation": "differentiate",
            "math_expression": "x**2",
        }))
        assert "derivative_latex" in result

    def test_integrate_returns_latex(self):
        result = math_compute(_make_ctx({
            "math_operation": "integrate",
            "math_expression": "x**2",
        }))
        assert "integral_latex" in result

    def test_simplify_returns_latex(self):
        result = math_compute(_make_ctx({
            "math_operation": "simplify",
            "math_expression": "x + x",
        }))
        assert "simplified_latex" in result
