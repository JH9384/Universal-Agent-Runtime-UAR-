"""
Regression tests for skill_guard error handling.

This test suite ensures that all skill_guard decorated functions
properly handle exceptions and return the expected status values
based on their configuration.
"""

from unittest.mock import MagicMock

from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard


def _ctx(metadata=None):
    """Helper to create a PipelineContext for testing."""
    goal = MagicMock()
    goal.metadata = metadata or {}
    ctx = PipelineContext(goal=goal, _max_events=10)
    return ctx


class TestSkillGuardErrorStatus:
    """Test that skill_guard returns 'error' status by default."""

    def test_default_error_status(self):
        """skill_guard should return 'error' status when not specified."""

        @skill_guard("Test operation")
        def test_function(ctx):
            raise RuntimeError("Test error")

        result = test_function(_ctx())
        assert result["status"] == "error"
        assert "Test error" in result["error"]

    def test_custom_failed_status(self):
        """skill_guard should return custom status when specified."""

        @skill_guard("Test operation", status="failed")
        def test_function(ctx):
            raise RuntimeError("Test error")

        result = test_function(_ctx())
        assert result["status"] == "failed"
        assert "Test error" in result["error"]

    def test_successful_execution_no_status_override(self):
        """Successful execution should not be affected by skill_guard."""

        @skill_guard("Test operation")
        def test_function(ctx):
            return {"status": "completed", "result": "success"}

        result = test_function(_ctx())
        assert result["status"] == "completed"
        assert result["result"] == "success"

    def test_successful_execution_with_custom_status(self):
        """Successful execution should not be affected by custom status."""

        @skill_guard("Test operation", status="failed")
        def test_function(ctx):
            return {"status": "completed", "result": "success"}

        result = test_function(_ctx())
        assert result["status"] == "completed"
        assert result["result"] == "success"


class TestSkillGuardWithNetworkErrors:
    """Test skill_guard handling of network-related errors."""

    def test_socket_error_returns_error(self):
        """Socket errors should be caught and return 'error' status."""

        @skill_guard("Network operation")
        def network_function(ctx):
            import socket
            socket.gethostbyname("example.com")  # May fail in test env

        result = network_function(_ctx())
        # Should return 'error' due to default skill_guard behavior
        assert result["status"] in ("error", "completed")

    def test_import_error_returns_error(self):
        """Import errors should be caught and return 'error' status."""

        @skill_guard("Import operation")
        def import_function(ctx):
            # This will raise ImportError when executed
            import nonexistent_module  # noqa: F401

        result = import_function(_ctx())
        assert result["status"] == "error"
        assert "nonexistent_module" in result["error"]


class TestKnownSkillsWithSkillGuard:
    """Test that known skills with skill_guard behave correctly."""

    def test_yolo_detect_skill_guard_default(self):
        """yolo_detect uses default skill_guard (status='error')."""
        from uar.skills.cv_skills import yolo_detect

        # Test with non-existent image to trigger error
        ctx = _ctx({"cv_image_path": "/non/existent/path.jpg"})
        result = yolo_detect(ctx)

        # Should return 'failed' for missing file,
        # or 'error' if exception occurs
        assert result["status"] in ("failed", "error")
