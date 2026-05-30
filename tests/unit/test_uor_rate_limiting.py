"""Tests for uar.uor.rate_limiting."""

import pytest

from uar.uor.rate_limiting import RateLimitInfo, RateLimiter, UORAPIClient


class TestRateLimitInfo:
    def test_to_dict(self):
        info = RateLimitInfo(
            allowed=True, remaining=5, reset_time=100.0, retry_after=10.0
        )
        d = info.to_dict()
        assert d["allowed"] is True
        assert d["remaining"] == 5
        assert d["reset_time"] == 100.0
        assert d["retry_after"] == 10.0


class TestRateLimiter:
    def test_reset_unknown_identifier(self):
        rl = RateLimiter()
        # Should not raise when identifier is unknown
        rl.reset("unknown")

    def test_is_allowed_empty_request_list(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        # First request should be allowed
        info = rl.is_allowed("id1")
        assert info.allowed is True
        # Reset and test edge case: empty request list
        rl.reset("id1")
        info = rl.is_allowed("id1")
        assert info.allowed is True


class TestUORAPIClient:
    def test_get_object_rate_limited(self):
        client = UORAPIClient("http://example.com")
        # Exhaust rate limit
        for _ in range(100):
            client.check_rate_limit("default")
        result = client.get_object("digest123")
        assert result is None

    def test_get_object_allowed_raises_not_implemented(self):
        client = UORAPIClient("http://example.com")
        with pytest.raises(NotImplementedError):
            client.get_object("digest123")

    def test_put_object_rate_limited(self):
        client = UORAPIClient("http://example.com")
        # Exhaust rate limit
        for _ in range(100):
            client.check_rate_limit("default")
        result = client.put_object({"key": "value"})
        assert result is None

    def test_put_object_allowed_raises_not_implemented(self):
        client = UORAPIClient("http://example.com")
        with pytest.raises(NotImplementedError):
            client.put_object({"key": "value"})
