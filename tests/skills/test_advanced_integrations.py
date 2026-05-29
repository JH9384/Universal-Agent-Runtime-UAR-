"""Tests for advanced integration skills missing-dep paths."""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.advanced_integrations import (
    llamaindex_rag,
    llamaindex_query,
    dagster_pipeline,
    dagster_status,
    flexible_graphrag,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestLlamaIndexRagMissingPackage:
    """llamaindex_rag when llama-index not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = llamaindex_rag(_ctx({}))
        assert result["status"] == "failed"


class TestLlamaIndexQueryMissingPackage:
    """llamaindex_query when llama-index not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = llamaindex_query(_ctx({}))
        assert result["status"] == "failed"


class TestDagsterPipelineMissingPackage:
    """dagster_pipeline when dagster not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = dagster_pipeline(_ctx({}))
        assert result["status"] == "failed"


class TestDagsterStatusMissingPackage:
    """dagster_status when dagster not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = dagster_status(_ctx({}))
        assert result["status"] == "failed"


class TestFlexibleGraphragMissingPackage:
    """flexible_graphrag when rdflib not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = flexible_graphrag(_ctx({}))
        assert result["status"] == "failed"
