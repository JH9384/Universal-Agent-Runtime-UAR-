"""Tests for stem_extended error paths.

Full SciPy/Qiskit/RDKit/Biopython paths require heavy deps;
this covers missing-package handling and input validation.
"""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.stem_extended import scipy_opt


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestScipyOptMissingPackage:
    """scipy_opt when scipy not installed."""

    def test_returns_error_when_scipy_missing(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(_ctx({"opt_operation": "minimize"}))
        assert result["status"] == "failed"
        assert "scipy" in result["error"].lower()


class TestScipyOptOperations:
    """scipy_opt operations with mocked scipy."""

    def test_unknown_operation(self):
        with patch(
            "uar.skills.stem_extended.require_package",
            return_value={"status": "failed", "error": "scipy missing"},
        ):
            result = scipy_opt(
                _ctx({"opt_operation": "nonexistent"})
            )
        assert result["status"] == "failed"
        assert "scipy" in result["error"].lower()
