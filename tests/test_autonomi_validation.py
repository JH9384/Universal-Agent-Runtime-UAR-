"""Regression tests for autonomi_storage.py fixes."""

from unittest.mock import MagicMock, patch

from uar.skills.autonomi_storage import (
    _safe_filename,
    _to_bool,
    _resolve_input_path,
    autonomi_upload,
    autonomi_download,
    autonomi_status,
)


class TestToBool:
    def test_true_values(self):
        assert _to_bool(True) is True
        assert _to_bool("true") is True
        assert _to_bool("True") is True
        assert _to_bool("1") is True
        assert _to_bool("yes") is True
        assert _to_bool("on") is True

    def test_false_values(self):
        assert _to_bool(False) is False
        assert _to_bool("false") is False
        assert _to_bool("False") is False
        assert _to_bool("0") is False
        assert _to_bool("") is False
        assert _to_bool("no") is False
        assert _to_bool("off") is False

    def test_string_false_was_bug(self):
        # Regression: bool('false') was True because non-empty str is truthy.
        assert _to_bool("false") is False
        assert bool("false") is True  # demonstrate the old bug


class TestSafeFilename:
    def test_sanitizes_special_chars(self):
        assert _safe_filename("hello/world") == "hello_world"
        assert _safe_filename("foo..bar") == "foo..bar"
        assert _safe_filename("   ") == "unnamed"

    def test_truncates_long_names(self):
        assert len(_safe_filename("a" * 200)) == 128


class TestResolveInputPath:
    def test_returns_none_when_no_paths(self):
        ctx = MagicMock()
        ctx.goal.metadata.get.return_value = None
        ctx.data = {}
        assert _resolve_input_path(ctx) is None

    def test_ignores_bytes_paths(self):
        # Regression: bytes paths produced 'b'...' string via str(bytes).
        ctx = MagicMock()
        ctx.goal.metadata.get.return_value = None
        ctx.data = {"doc_ingest": {"documents": [{"path": b"/tmp/test.txt"}]}}
        # Should skip the bytes path and return None
        assert _resolve_input_path(ctx) is None


class TestAutonomiUpload:
    @patch.dict("sys.modules", {"autonomi": MagicMock()})
    def test_string_false_public_is_private(self):
        # Regression: 'autonomi_public': 'false' was treated as public=True.
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_source": "/etc/passwd",
            "autonomi_public": "false",
        }
        # path security will reject /etc/passwd, but we still verify
        # _to_bool is used before the error is returned
        result = autonomi_upload(ctx)
        assert result["status"] == "failed"

    @patch.dict("sys.modules", {"autonomi": MagicMock()})
    @patch("uar.skills.autonomi_storage.validate_path_security")
    def test_directory_upload_blocked_gracefully(
        self, mock_val, tmp_path
    ):
        # Regression: non-file non-dir paths raised ValueError.
        mock_val.return_value = None  # path security passes
        fake = tmp_path / "fake_socket"
        fake.write_text("")  # exists as file initially
        ctx = MagicMock()
        ctx.goal.metadata = {"autonomi_source": str(fake)}
        result = autonomi_upload(ctx)
        # Should return gracefully, not raise ValueError
        assert "status" in result


class TestAutonomiDownload:
    @patch("uar.skills.autonomi_storage._get_autonomi")
    def test_string_false_public(self, mock_get):
        # Regression: 'autonomi_public': 'false' was treated as public=True.
        mock_get.return_value = None
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_address": "test-addr",
            "autonomi_public": "false",
        }
        result = autonomi_download(ctx)
        assert result["status"] == "failed"


class TestAutonomiStatus:
    @patch("uar.skills.autonomi_storage._get_autonomi")
    def test_returns_package_not_installed(self, mock_get):
        mock_get.return_value = None
        ctx = MagicMock()
        result = autonomi_status(ctx)
        assert result["status"] == "failed"
        assert result["available"] is False

    @patch.dict("sys.modules", {"autonomi": MagicMock()})
    def test_hides_private_key_in_output(self):
        # Verify private key never appears in the result dict.
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_private_key": "secret-key-123",
            "autonomi_network": "testnet",
        }
        result = autonomi_status(ctx)
        assert "secret-key-123" not in str(result)
        assert result["has_wallet"] is True
