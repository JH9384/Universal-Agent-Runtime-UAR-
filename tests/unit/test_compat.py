"""Tests for uar.core.compat utilities."""

from unittest.mock import patch

from uar.core.compat import lazy_import


class TestLazyImport:
    def test_returns_module_when_installed(self):
        result = lazy_import("os")
        assert result is not None
        assert result.__name__ == "os"

    def test_returns_none_when_missing(self):
        result = lazy_import("definitely_not_a_real_module_12345")
        assert result is None

    @patch("importlib.import_module", side_effect=ImportError("no module"))
    def test_import_error_handled(self, mock_import):
        result = lazy_import("foo")
        assert result is None
        mock_import.assert_called_once_with("foo")
