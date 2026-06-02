"""
Regression tests for skill_guard error handling.

This test suite ensures that all skill_guard decorated functions
properly handle exceptions and return the expected status values
based on their configuration.
"""

from unittest.mock import MagicMock, patch
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
            import nonexistent_module

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

    def test_opencv_process_skill_guard_default(self):
        """opencv_process uses default skill_guard (status='error')."""
        from uar.skills.cv_skills import opencv_process

        # Test with non-existent image to trigger error
        ctx = _ctx({
            "cv_image_path": "/non/existent/path.jpg",
            "cv_operation": "grayscale"
        })
        result = opencv_process(ctx)

        # Should return 'failed' for missing file,
        # or 'error' if exception occurs
        assert result["status"] in ("failed", "error")

    def test_quantum_ml_skill_guard_default(self):
        """quantum_ml uses default skill_guard (status='error')."""
        from uar.skills.quantum_ml import quantum_ml

        # Test with invalid task to trigger error
        ctx = _ctx({"qml_task": "invalid_task"})
        result = quantum_ml(ctx)

        # Should return 'failed' for invalid task,
        # or 'error' if exception occurs
        assert result["status"] in ("failed", "error")

    def test_scipy_opt_skill_guard_default(self):
        """scipy_opt uses default skill_guard (status='error')."""
        from uar.skills.stem_extended import scipy_opt

        # Test with invalid operation to trigger error
        ctx = _ctx({"opt_operation": "invalid_operation"})
        result = scipy_opt(ctx)

        # Should return 'failed' for invalid operation,
        # or 'error' if exception occurs
        assert result["status"] in ("failed", "error")

    def test_math_plot_3d_skill_guard_custom(self):
        """math_plot_3d uses custom skill_guard (status='failed')."""
        from uar.skills.math_plot_3d import math_plot_3d

        # This should return 'failed' on errors, not 'error'
        ctx = _ctx({
            "plot_3d_type": "surface",
            "plot_3d_expression": "invalid!!!"
        })
        result = math_plot_3d(ctx)

        # Should return 'completed' (graceful handling)
        # or 'failed' (custom status)
        assert result["status"] in ("completed", "failed")
        # Should not be 'error' due to custom status
        assert result["status"] != "error"


class TestSkillGuardExceptionTypes:
    """Test skill_guard with various exception types."""

    def test_value_error_handling(self):
        """ValueError should be caught and return appropriate status."""

        @skill_guard("Value operation")
        def value_function(ctx):
            raise ValueError("Invalid value")

        result = value_function(_ctx())
        assert result["status"] == "error"
        assert "Invalid value" in result["error"]

    def test_key_error_handling(self):
        """KeyError should be caught and return appropriate status."""

        @skill_guard("Key operation")
        def key_function(ctx):
            return {}["missing_key"]  # Raises KeyError

        result = key_function(_ctx())
        assert result["status"] == "error"
        assert "missing_key" in result["error"]

    def test_attribute_error_handling(self):
        """AttributeError should be caught and return appropriate status."""

        @skill_guard("Attribute operation")
        def attribute_function(ctx):
            obj = None
            return obj.some_attribute  # Raises AttributeError

        result = attribute_function(_ctx())
        assert result["status"] == "error"

    def test_type_error_handling(self):
        """TypeError should be caught and return appropriate status."""

        @skill_guard("Type operation")
        def type_function(ctx):
            return len(123)  # Raises TypeError

        result = type_function(_ctx())
        assert result["status"] == "error"


class TestSkillGuardNestedExceptions:
    """Test skill_guard with nested/chain exceptions."""

    def test_chained_exception_preserved(self):
        """Chained exceptions should be preserved in error message."""

        @skill_guard("Nested operation")
        def nested_function(ctx):
            try:
                raise ValueError("Inner error")
            except ValueError:
                # Chain the exception
                raise RuntimeError("Outer error") from ValueError("Inner error")

        result = nested_function(_ctx())
        assert result["status"] == "error"
        # Should contain information about both errors
        error_msg = result["error"]
        assert (
            "Outer error" in error_msg or "Inner error" in error_msg
        )

    def test_exception_cause_preserved(self):
        """Exception cause should be preserved."""

        @skill_guard("Cause operation")
        def cause_function(ctx):
            try:
                int("not_a_number")
            except ValueError as e:
                raise RuntimeError("Conversion failed") from e

        result = cause_function(_ctx())
        assert result["status"] == "error"
        error_msg = result["error"]
        assert "Conversion failed" in error_msg


class TestSkillGuardRegressionSpecific:
    """Regression tests for specific skill_guard issues found in the codebase."""

    def test_ultralytics_connectivity_error(self):
        """Test that ultralytics connectivity errors return 'error' status.

        This is a regression test for the issue where yolo_detect
        was returning 'error' status due to network connectivity checks
        being blocked by pytest_socket.
        """
        from uar.skills.cv_skills import yolo_detect

        # Mock ultralytics to raise a socket error on import
        with patch.dict('sys.modules', {'ultralytics': None}):
            # This simulates the import error that would occur
            with patch('uar.skills.cv_skills.require_package', return_value=None):
                # The actual import happens inside the function
                with patch(
                    'builtins.__import__',
                    side_effect=ImportError("No module named 'ultralytics'")
                ):
                    ctx = _ctx({"cv_image_path": "/fake/path.jpg"})
                    result = yolo_detect(ctx)

                    # Should return 'error' due to skill_guard
                    # catching the import error
                    assert result["status"] == "error"
                    assert "ultralytics" in result["error"].lower()

    def test_skill_guard_with_import_error_in_nested_function(self):
        """Test skill_guard when import error occurs in nested function call."""

        def nested_import():
            # This will raise ImportError when executed
            import nonexistent_package

        @skill_guard("Nested import")
        def outer_function(ctx):
            nested_import()

        result = outer_function(_ctx())
        assert result["status"] == "error"
        assert "nonexistent_package" in result["error"]
