"""Tests for stem_extended SymPy fallback paths.

Full SciPy/Qiskit/RDKit/Biopython paths require heavy deps;
this covers the SymPy fallback paths that work without them.
"""

from unittest.mock import patch

import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.stem_extended import scipy_opt, diff_eq_solve


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestScipyOptSympyFallback:
    """scipy_opt via SymPy when SciPy is missing."""

    def test_minimize_parabola(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "minimize", "opt_function": "x**2"})
            )
        assert result["status"] == "completed"
        assert result["optimum"] == pytest.approx(0.0, abs=1e-6)

    def test_maximize_inverted_parabola(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "maximize", "opt_function": "-x**2"})
            )
        assert result["status"] == "completed"
        assert result["optimum"] == pytest.approx(0.0, abs=1e-6)

    def test_integrate_definite(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "integrate",
                    "opt_function": "x**2",
                    "opt_bounds": [0, 3],
                })
            )
        assert result["status"] == "completed"
        assert result["value"] == pytest.approx(9.0, abs=1e-6)

    def test_eigenvalues_identity(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "eig",
                    "opt_matrix_a": [[1, 0], [0, 1]],
                })
            )
        assert result["status"] == "completed"

    def test_root_find(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "root",
                    "opt_function": "x**2 - 4",
                    "opt_initial": 1.5,
                })
            )
        assert result["status"] == "completed"
        r = result["root"]
        assert abs(r - 2.0) < 1e-6 or abs(r + 2.0) < 1e-6

    def test_unknown_operation(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "nonexistent"})
            )
        assert result["status"] == "failed"


class TestDiffEqSolveSympyFallback:
    """diff_eq_solve via SymPy when SciPy is missing."""

    def test_exponential_growth(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = diff_eq_solve(
                _ctx({"de_equation": "f(x).diff(x) - f(x)"})
            )
        assert result["status"] == "completed"
        assert "exp" in result["solution"].lower()

    def test_second_order_ode(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = diff_eq_solve(
                _ctx({"de_equation": "f(x).diff(x, 2) + f(x)"})
            )
        assert result["status"] == "completed"
