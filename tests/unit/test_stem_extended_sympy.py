"""Tests for stem_extended SymPy fallback paths in tests/unit/."""

from unittest.mock import MagicMock, patch

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
    def test_minimize(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "minimize", "opt_function": "x**2"})
            )
        assert result["status"] == "completed"
        assert result["optimum"] == pytest.approx(0.0, abs=1e-6)

    def test_maximize(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "maximize", "opt_function": "-x**2"})
            )
        assert result["status"] == "completed"
        assert result["optimum"] == pytest.approx(0.0, abs=1e-6)

    def test_maximize_with_bounds(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "maximize",
                    "opt_function": "-x**2",
                    "opt_bounds": [-2, 2],
                })
            )
        assert result["status"] == "completed"

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

    def test_integrate_indefinite(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "integrate", "opt_function": "x**2"})
            )
        assert result["status"] == "completed"
        assert "symbolic" in result

    def test_eig(self):
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
        assert "eigenvalues" in result

    def test_eig_non_square(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "eig",
                    "opt_matrix_a": [[1, 0, 0], [0, 1, 0]],
                })
            )
        assert result["status"] == "failed"

    def test_solve_linear(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "solve_linear",
                    "opt_matrix": [[2, 1], [1, -1]],
                    "opt_rhs": [3, 0],
                })
            )
        assert result["status"] == "completed"

    def test_solve_linear_mismatch(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "solve_linear",
                    "opt_matrix": [[1, 0]],
                    "opt_rhs": [0, 0],
                })
            )
        assert result["status"] == "failed"

    def test_root(self):
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

    def test_root_no_convergence(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "root",
                    "opt_function": "x**2 + 1",
                    "opt_initial": 1.0,
                })
            )
        assert result["status"] == "failed"

    def test_unknown_operation(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "nonexistent"})
            )
        assert result["status"] == "failed"

    def test_linprog(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "linprog",
                    "opt_function": "x",
                    "opt_constraints": ["x <= 1"],
                })
            )
        assert result["status"] == "completed"
        assert "optimum" in result

    def test_linprog_no_feasible(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "linprog",
                    "opt_function": "x",
                    "opt_constraints": ["x <= -1", "x >= 1"],
                })
            )
        assert result["status"] == "failed"
        assert "no feasible point" in result["error"]

    def test_minimize_no_critical_points(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "minimize",
                    "opt_function": "x**2 + 1",
                    "opt_bounds": [2, 3],
                })
            )
        assert result["status"] == "completed"

    def test_solve_linear_exception(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({
                    "opt_operation": "solve_linear",
                    "opt_matrix": [[0, 0], [0, 0]],
                    "opt_rhs": [1, 1],
                })
            )
        assert result["status"] == "failed"


class TestDiffEqSolveSympyFallback:
    def test_basic(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = diff_eq_solve(
                _ctx({"de_equation": "f(x).diff(x) - f(x)"})
            )
        assert result["status"] == "completed"
        assert "exp" in result["solution"].lower()

    def test_second_order(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = diff_eq_solve(
                _ctx({"de_equation": "f(x).diff(x, 2) + f(x)"})
            )
        assert result["status"] == "completed"
        assert "solution" in result

    def test_with_initial_conditions(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = diff_eq_solve(
                _ctx({
                    "de_equation": "f(x).diff(x) - f(x)",
                    "de_initial": {"f(0)": 1},
                })
            )
        assert "status" in result

    def test_list_solutions(self):
        mock_sol = MagicMock()
        mock_sol.rhs = "sol1"
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            with patch("sympy.dsolve", return_value=[mock_sol, mock_sol]):
                result = diff_eq_solve(
                    _ctx({"de_equation": "f(x).diff(x) - f(x)"})
                )
        assert result["status"] == "completed"
        assert "num_solutions" in result

    def test_dsolve_exception(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            with patch("sympy.dsolve", side_effect=ValueError("bad eq")):
                result = diff_eq_solve(
                    _ctx({"de_equation": "f(x).diff(x) - f(x)"})
                )
        assert result["status"] == "failed"
        assert "dsolve failed" in result["error"]
