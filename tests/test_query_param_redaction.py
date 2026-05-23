"""Tests for query parameter redaction in request logging.

Covers: sensitive keys masked, non-sensitive keys preserved,
case-insensitive matching, empty query handling.
"""

from __future__ import annotations

import pytest
from urllib.parse import urlparse

from uar.api.middleware import _redact_query_params, _SENSITIVE_QUERY_KEYS


class TestRedactQueryParams:
    def _url(self, query: str):
        return urlparse(f"http://example.com/api/run?{query}")

    @pytest.mark.parametrize("key", list(_SENSITIVE_QUERY_KEYS))
    def test_sensitive_keys_redacted(self, key):
        url = self._url(f"{key}=secret_value&foo=bar")
        result = _redact_query_params(url)
        assert "***" in result
        assert "secret_value" not in result
        assert "foo=bar" in result

    def test_non_sensitive_keys_preserved(self):
        url = self._url("page=1&limit=10&sort=desc")
        result = _redact_query_params(url)
        assert "page=1" in result
        assert "limit=10" in result
        assert "sort=desc" in result

    def test_mixed_sensitive_and_normal(self):
        url = self._url("token=abc123&foo=bar&secret=shh")
        result = _redact_query_params(url)
        assert "token=***" in result
        assert "secret=***" in result
        assert "foo=bar" in result
        assert "abc123" not in result
        assert "shh" not in result

    def test_empty_query_returns_empty(self):
        url = urlparse("http://example.com/api/run")
        result = _redact_query_params(url)
        assert result == ""

    def test_case_insensitive_matching(self):
        url = self._url("TOKEN=abc&API_KEY=xyz")
        result = _redact_query_params(url)
        assert "TOKEN=***" in result
        assert "API_KEY=***" in result

    def test_multiple_values_for_same_key(self):
        url = self._url("token=first&token=second&foo=bar")
        result = _redact_query_params(url)
        # Both values should be redacted
        assert result.count("***") == 2
        assert "first" not in result
        assert "second" not in result
