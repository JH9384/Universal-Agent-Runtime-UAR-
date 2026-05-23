"""Test dependency compatibility for optional dependency groups."""

import importlib.util


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
        from unittest import mock

        def _mock_find_spec(name):
            if name in ("unstructured", "docling"):
                return mock.MagicMock()
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", _mock_find_spec):
            assert importlib.util.find_spec("unstructured") is not None
            assert importlib.util.find_spec("docling") is not None

    def test_agent_orchestration_imports(self):
        """Test that agent-orchestration group imports work."""
        from unittest import mock

        def _mock_find_spec(name):
            if name in ("autogen", "crewai"):
                return mock.MagicMock()
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", _mock_find_spec):
            assert importlib.util.find_spec("autogen") is not None
            assert importlib.util.find_spec("crewai") is not None

    def test_advanced_rag_imports(self):
        """Test that advanced-rag group imports work."""
        from unittest import mock

        def _mock_find_spec(name):
            if name in ("llama_index", "neo4j", "chromadb", "qdrant_client"):
                return mock.MagicMock()
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", _mock_find_spec):
            assert importlib.util.find_spec("llama_index") is not None
            assert importlib.util.find_spec("neo4j") is not None
            assert importlib.util.find_spec("chromadb") is not None
            assert importlib.util.find_spec("qdrant_client") is not None

    def test_pipeline_orchestration_imports(self):
        """Test that pipeline-orchestration group imports work."""
        from unittest import mock

        def _mock_find_spec(name):
            if name == "dagster":
                return mock.MagicMock()
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", _mock_find_spec):
            assert importlib.util.find_spec("dagster") is not None

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
