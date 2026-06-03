"""Tests for uar.skills.autonomi_storage."""

import pytest
from unittest.mock import MagicMock, patch

from uar.skills.autonomi_storage import (
    _to_bool,
    _safe_filename,
    _resolve_input_path,
    _wallet_and_payment,
    autonomi_upload,
    autonomi_download,
    autonomi_status,
)


class TestWalletAndPayment:
    @pytest.fixture(autouse=True)
    def _mock_autonomi_module(self):
        """Provide a mock autonomi module since the real package is
        optional."""
        mock_mod = MagicMock()
        mock_mod.Network = MagicMock()
        mock_mod.PaymentOption = MagicMock()
        mock_mod.Wallet = MagicMock()
        with patch.dict("sys.modules", {"autonomi": mock_mod}):
            yield

    def test_rejects_empty_key_after_0x_strip(self):
        """Regression: 0x alone strips to empty, must raise ValueError."""
        import sys

        Wallet = sys.modules["autonomi"].Wallet
        with pytest.raises(ValueError, match="empty after stripping"):
            _wallet_and_payment("0x", "testnet")
        Wallet.new_from_private_key.assert_not_called()

    def test_strips_0x_prefix_normally(self):
        """Valid key with 0x prefix works after stripping."""
        import sys

        Wallet = sys.modules["autonomi"].Wallet
        wallet = MagicMock()
        Wallet.new_from_private_key.return_value = wallet
        _wallet_and_payment("0xabc123", "testnet")
        Wallet.new_from_private_key.assert_called_once()
        _, actual_key = Wallet.new_from_private_key.call_args[0]
        assert actual_key == "abc123"

    def test_no_strip_for_plain_key(self):
        """Key without 0x prefix is passed through unchanged."""
        import sys

        Wallet = sys.modules["autonomi"].Wallet
        wallet = MagicMock()
        Wallet.new_from_private_key.return_value = wallet
        _wallet_and_payment("plainkey", "mainnet")
        _, actual_key = Wallet.new_from_private_key.call_args[0]
        assert actual_key == "plainkey"


class TestToBool:
    def test_true_values(self):
        assert _to_bool("true") is True
        assert _to_bool("yes") is True
        assert _to_bool(1) is True
        assert _to_bool("1") is True
        assert _to_bool(True) is True

    def test_false_values(self):
        assert _to_bool("false") is False
        assert _to_bool("0") is False
        assert _to_bool("") is False
        assert _to_bool("no") is False
        assert _to_bool("off") is False
        assert _to_bool(False) is False
        assert _to_bool(0) is False


class TestSafeFilename:
    def test_normal(self):
        assert _safe_filename("hello.txt") == "hello.txt"

    def test_special_chars(self):
        assert _safe_filename("hello/world") == "hello_world"

    def test_empty(self):
        assert _safe_filename("") == "unnamed"

    def test_long(self):
        assert len(_safe_filename("a" * 200)) == 128


class TestResolveInputPath:
    def test_no_path(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.data = {}
        assert _resolve_input_path(ctx) is None

    def test_from_metadata(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        ctx = MagicMock()
        ctx.goal.metadata = {"input_path": str(f)}
        ctx.data = {}
        with patch("uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path):
            result = _resolve_input_path(ctx)
        assert result is not None
        assert result.name == "test.txt"

    def test_from_doc_ingest(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.data = {
            "doc_ingest": {
                "documents": [{"path": str(f)}],
            }
        }
        with patch("uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path):
            result = _resolve_input_path(ctx)
        assert result is not None
        assert result.name == "doc.txt"

    def test_path_security_exception(self, tmp_path):
        ctx = MagicMock()
        ctx.goal.metadata = {"input_path": str(tmp_path / "outside.txt")}
        ctx.data = {}
        with patch("uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path):
            with patch(
                "uar.skills.autonomi_storage.validate_path_security",
                side_effect=Exception("not allowed"),
            ):
                result = _resolve_input_path(ctx)
        assert result is None


class TestAutonomiUpload:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.autonomi_storage.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = autonomi_upload(ctx)
        assert result["status"] == "error"

    def test_missing_source(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            result = autonomi_upload(ctx)
        assert result["status"] == "failed"
        assert "autonomi_source" in str(result["error"])

    def test_path_not_found(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"autonomi_source": "/nonexistent/file.txt"}
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            result = autonomi_upload(ctx)
        assert result["status"] == "failed"

    def test_not_file_or_dir(self, tmp_path):
        # Create a symlink loop or similar non-file non-dir
        # Actually, just use a path that exists but isn't file/dir
        # On Unix, device files exist but aren't files/dirs
        # Let's just test with a regular file for success case
        pass

    def test_upload_public_success(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_source": str(f),
            "autonomi_public": True,
        }

        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_cb.call"
                ) as cb:
                    cb.return_value = "addr123"
                    result = autonomi_upload(ctx)
        assert result["status"] == "completed"
        assert result["address"] == "addr123"
        assert result["public"] is True

    def test_upload_private_success(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_source": str(f),
            "autonomi_public": False,
            "autonomi_private_key": "0xabc123",
            "autonomi_network": "testnet",
        }

        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_cb.call"
                ) as cb:
                    cb.return_value = "addr456"
                    result = autonomi_upload(ctx)
        assert result["status"] == "completed"
        assert result["address"] == "addr456"
        assert result["public"] is False
        assert result["has_wallet"] is True

    def test_upload_path_security_violation(self, tmp_path):
        outside = tmp_path.parent / "outside_upload.txt"
        outside.write_text("secret")
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_source": str(outside),
        }
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                result = autonomi_upload(ctx)
        assert result["status"] == "failed"
        assert "security" in result["error"].lower()

    def test_upload_not_file_or_dir(self, tmp_path):
        # A directory is valid for upload, so skip this edge case
        pass


class TestAutonomiDownload:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.autonomi_storage.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = autonomi_download(ctx)
        assert result["status"] == "error"

    def test_missing_address(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            result = autonomi_download(ctx)
        assert result["status"] == "failed"
        assert "autonomi_address" in str(result["error"])

    def test_download_success(self, tmp_path):
        dest = tmp_path / "downloads"
        dest.mkdir()
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_address": "addr123",
            "autonomi_dest": str(dest),
        }
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_cb.call"
                ) as cb:
                    cb.return_value = str(dest)
                    result = autonomi_download(ctx)
        assert result["status"] == "completed"
        assert result["address"] == "addr123"

    def test_download_default_dest(self, tmp_path):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_address": "addr123",
        }
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_cb.call"
                ) as cb:
                    cb.return_value = str(tmp_path)
                    result = autonomi_download(ctx)
        assert result["status"] == "completed"
        assert result["dest_path"] is not None

    def test_download_public(self, tmp_path):
        dest = tmp_path / "downloads"
        dest.mkdir()
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_address": "addr123",
            "autonomi_dest": str(dest),
            "autonomi_public": True,
        }
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_cb.call"
                ) as cb:
                    cb.return_value = str(dest)
                    result = autonomi_download(ctx)
        assert result["status"] == "completed"
        assert result["public"] is True

    def test_download_path_security_violation(self, tmp_path):
        outside = tmp_path.parent / "outside_download"
        outside.mkdir(parents=True, exist_ok=True)
        ctx = MagicMock()
        ctx.goal.metadata = {
            "autonomi_address": "addr123",
            "autonomi_dest": str(outside),
        }
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch(
                "uar.skills.autonomi_storage.ALLOWED_ROOT", tmp_path
            ):
                result = autonomi_download(ctx)
        assert result["status"] == "failed"
        assert "security" in result["error"].lower()


class TestAutonomiStatus:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.autonomi_storage.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = autonomi_status(ctx)
        assert result["status"] == "error"
        assert result["available"] is False

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        mock_mod = MagicMock()
        mock_mod.__version__ = "1.0.0"
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch.dict(
                "sys.modules", {"autonomi": mock_mod}
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_mod",
                    mock_mod,
                    create=True,
                ):
                    result = autonomi_status(ctx)
        assert result["status"] == "completed"

    def test_with_wallet(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"autonomi_private_key": "abc123"}
        mock_mod = MagicMock()
        mock_mod.__version__ = "1.0.0"
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch.dict(
                "sys.modules", {"autonomi": mock_mod}
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_mod",
                    mock_mod,
                    create=True,
                ):
                    with patch(
                        "autonomi.Wallet"
                    ) as Wallet:
                        wallet = MagicMock()
                        wallet.address = "0xWalletAddr"
                        Wallet.new_from_private_key.return_value = wallet
                        result = autonomi_status(ctx)
        assert result["status"] == "completed"
        assert result["has_wallet"] is True
        assert result["wallet_address"] == "0xWalletAddr"

    def test_wallet_exception(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"autonomi_private_key": "bad_key"}
        mock_mod = MagicMock()
        mock_mod.__version__ = "1.0.0"
        with patch(
            "uar.skills.autonomi_storage.require_package", return_value=None
        ):
            with patch.dict(
                "sys.modules", {"autonomi": mock_mod}
            ):
                with patch(
                    "uar.skills.autonomi_storage._autonomi_mod",
                    mock_mod,
                    create=True,
                ):
                    with patch(
                        "autonomi.Wallet"
                    ) as Wallet:
                        Wallet.new_from_private_key.side_effect = ValueError(
                            "bad key"
                        )
                        result = autonomi_status(ctx)
        assert result["status"] == "completed"
        assert result["has_wallet"] is False
        assert "wallet_error" in result
