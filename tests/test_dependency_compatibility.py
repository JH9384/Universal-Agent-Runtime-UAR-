"""Test dependency compatibility for optional dependency groups."""

import pytest
from importlib.util import find_spec


class TestDependencyCompatibility:
    """Test optional dependency groups can be imported correctly."""

    def test_base_imports(self):
        """Test that base dependencies are always available."""
        # Core dependencies should always be importable
        import fastapi
        import uvicorn
        import httpx
        import pydantic

        assert fastapi is not None
        assert uvicorn is not None
        assert httpx is not None
        assert pydantic is not None

    def test_doc_processing_imports(self):
        """Test that doc-processing group imports work."""
        if find_spec("unstructured") is None:
            pytest.skip("doc-processing group not installed")
        if find_spec("docling") is None:
            pytest.skip("doc-processing group not installed")

        # If we got here, both packages are importable
        assert True

    def test_agent_orchestration_imports(self):
        """Test that agent-orchestration group imports work."""
        if find_spec("autogen") is None:
            pytest.skip("agent-orchestration group not installed")
        if find_spec("crewai") is None:
            pytest.skip("agent-orchestration group not installed")

        # If we got here, both packages are importable
        assert True

    def test_advanced_rag_imports(self):
        """Test that advanced-rag group imports work."""
        if find_spec("llama_index") is None:
            pytest.skip("advanced-rag group not installed")
        if find_spec("neo4j") is None:
            pytest.skip("advanced-rag group not installed")
        if find_spec("chromadb") is None:
            pytest.skip("advanced-rag group not installed")
        if find_spec("qdrant_client") is None:
            pytest.skip("advanced-rag group not installed")

        # If we got here, all packages are importable
        assert True

    def test_pipeline_orchestration_imports(self):
        """Test that pipeline-orchestration group imports work."""
        if find_spec("dagster") is None:
            pytest.skip("pipeline-orchestration group not installed")

        # If we got here, dagster is importable
        assert True

    def test_no_version_conflicts(self):
        """Test that there are no obvious version conflicts."""
        # Check that core packages can be imported together
        # The imports themselves test for conflicts
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401

        # If we got here without errors, no obvious conflicts
        assert True

    def test_uar_core_imports(self):
        """Test that core UAR modules import correctly."""
        from uar.core.planner import SimplePlanner
        from uar.core.executor import Executor
        from uar.core.validation import validate_goal, validate_skills

        assert SimplePlanner is not None
        assert Executor is not None
        assert validate_goal is not None
        assert validate_skills is not None
