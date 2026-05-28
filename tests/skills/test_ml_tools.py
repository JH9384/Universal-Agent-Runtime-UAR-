"""Tests for ml_tools error paths.

Full Optuna/ChromaDB paths require heavy deps; this covers
missing-package handling and input validation.
"""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.ml_tools import optuna_tune, chromadb_store


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestOptunaTuneMissingPackage:
    """optuna_tune when optuna not installed."""

    def test_returns_error_when_optuna_missing(self):
        with patch(
            "uar.skills.ml_tools.require_package",
            return_value={"status": "failed", "error": "optuna missing"},
        ):
            result = optuna_tune(_ctx({"optuna_objective": "x**2"}))
        assert result["status"] == "failed"
        assert "optuna" in result["error"].lower()


class TestChromaDBStoreMissingPackage:
    """chromadb_store when chromadb not installed."""

    def test_returns_error_when_chromadb_missing(self):
        with patch(
            "uar.skills.ml_tools.require_package",
            return_value={"status": "failed", "error": "chromadb missing"},
        ):
            result = chromadb_store(_ctx({"chroma_operation": "query"}))
        assert result["status"] == "failed"
        assert "chromadb" in result["error"].lower()

    def test_query_operation_no_chromadb(self):
        """query operation when chromadb is missing."""
        with patch(
            "uar.skills.ml_tools.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = chromadb_store(_ctx({"chroma_operation": "query"}))
        assert result["status"] == "failed"
