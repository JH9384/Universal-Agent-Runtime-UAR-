"""Tests for UOR address derivation compatibility layer.

Covers both native (uor-addr) and fallback (RFC 8785) paths.
"""

from unittest.mock import patch, MagicMock

import pytest

from uar.compat.uor_address import (
    UORAddressError,
    address_for_json,
    address_with_witness,
    _to_json_bytes,
    _address_via_native,
)


class TestToJsonBytes:
    """JSON serialization helper."""

    def test_serializes_dict(self):
        result = _to_json_bytes({"a": 1})
        assert result == b'{"a":1}'

    def test_non_serializable_raises(self):
        with pytest.raises(UORAddressError, match="not JSON serializable"):
            _to_json_bytes({"a": object()})  # type: ignore[dict-item]


class TestAddressViaNative:
    """Native uor-addr path."""

    def test_calls_kappa_json_address(self):
        pytest.importorskip("uor_addr")
        mock_kappa = MagicMock()
        mock_kappa.json_address.return_value = "uor://test"
        with patch("uar.compat.uor_address.kappa", mock_kappa):
            result = _address_via_native(b'{"a":1}')
        assert result == "uor://test"
        mock_kappa.json_address.assert_called_once()

    def test_native_error_wrapped(self):
        pytest.importorskip("uor_addr")
        from uor_addr import AddressError as RealAddrErr

        mock_kappa = MagicMock()
        mock_kappa.json_address.side_effect = RealAddrErr("native failed")
        with patch("uar.compat.uor_address.kappa", mock_kappa):
            with pytest.raises(UORAddressError, match="native failed"):
                _address_via_native(b'{"a":1}')


class TestAddressForJson:
    """Public API: derive canonical address."""

    def test_returns_address(self):
        addr = address_for_json({"hello": "world"})
        assert addr.startswith("sha256:") or addr.startswith("uor://")

    def test_same_data_same_address(self):
        addr1 = address_for_json({"x": 1, "y": 2})
        addr2 = address_for_json({"y": 2, "x": 1})
        assert addr1 == addr2

    def test_nested_data(self):
        addr = address_for_json({"a": {"b": [1, 2, 3]}})
        assert addr.startswith("sha256:") or addr.startswith("uor://")


class TestAddressWithWitness:
    """Witness payload generation."""

    def test_native_returns_witness(self):
        pytest.importorskip("uor_addr")
        mock_kappa = MagicMock()
        mock_grounded = MagicMock()
        mock_grounded.kappa_label.return_value = "uor://label"
        mock_grounded.content_fingerprint.return_value = b"\x01\x02\x03"
        mock_grounded.verify.return_value = True
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda *a: mock_grounded
        mock_ctx.__exit__ = lambda *a: None
        mock_kappa.json_address_with_witness.return_value = mock_ctx

        with patch("uar.compat.uor_address.kappa", mock_kappa):
            with patch(
                "uar.compat.uor_address._HAS_NATIVE", True
            ):
                with patch.object(
                    mock_kappa, "json_address_with_witness",
                    create=True, return_value=mock_ctx,
                ):
                    addr, witness = address_with_witness(
                        {"test": 1}
                    )

        assert addr == "uor://label"
        assert witness is not None
        assert witness["fingerprint"] == "010203"
        assert witness["verified_label"] is True

    def test_native_missing_attribute_fallback(self):
        """If kappa lacks json_address_with_witness, fallback."""
        pytest.importorskip("uor_addr")
        mock_kappa = MagicMock(spec=[])
        with patch("uar.compat.uor_address.kappa", mock_kappa):
            with patch(
                "uar.compat.uor_address._address_via_rfc8785",
                return_value="sha256:fallback",
            ):
                addr, witness = address_with_witness({"test": 1})
        assert addr == "sha256:fallback"
        assert witness is None
