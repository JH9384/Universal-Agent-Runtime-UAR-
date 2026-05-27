"""Regression tests for extended review findings.

Covers HTTP client lifecycle and resource cleanup.
"""

from unittest.mock import MagicMock


class TestUorEcosystemHTTPClientLifecycle:
    """Module-level httpx client must be closable without error."""

    def test_close_http_client_idempotent(self):
        from uar.core.uor_ecosystem import _close_http_client

        # Should not raise even when client was never created
        _close_http_client()

    def test_close_http_client_clears_reference(self, monkeypatch):
        from uar.core import uor_ecosystem as mod

        mock_client = MagicMock()
        monkeypatch.setattr(mod, "_http_client", mock_client)
        mod._close_http_client()
        mock_client.close.assert_called_once()
        assert mod._http_client is None


class TestAtomicLangModelHTTPClientLifecycle:
    """ALM module-level httpx client must be closable without error."""

    def test_close_http_client_idempotent(self):
        from uar.skills.atomic_lang_model import _close_http_client

        _close_http_client()

    def test_close_http_client_clears_reference(self, monkeypatch):
        from uar.skills import atomic_lang_model as mod

        mock_client = MagicMock()
        monkeypatch.setattr(mod, "_http_client", mock_client)
        mod._close_http_client()
        mock_client.close.assert_called_once()
        assert mod._http_client is None
