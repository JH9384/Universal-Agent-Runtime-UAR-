"""Tests for UOR Ecosystem integration layer."""

import os

from uar.core.uor_ecosystem import (
    UORAddrClient,
    HologramClient,
    MoltbookClient,
    PrismBTCClient,
    SeveranceAIClient,
    AnunixClient,
    UORFoundationClient,
    UOREcosystem,
    get_uor_ecosystem,
    reset_uor_ecosystem,
    _http_post,
    _http_get,
)


class TestUORAddrClient:
    def test_canonicalize_produces_envelope(self):
        client = UORAddrClient()
        env = client.canonicalize({"hello": "world"})
        assert "digest" in env
        assert env["digest"].startswith("sha256:")
        assert "size" in env
        assert "mediaType" in env
        assert env["mediaType"] == "application/uor-addr-1+json"

    def test_canonicalize_deterministic(self):
        client = UORAddrClient()
        env1 = client.canonicalize({"a": 1, "b": 2})
        env2 = client.canonicalize({"b": 2, "a": 1})
        assert env1["digest"] == env2["digest"]

    def test_wrap_with_uor(self):
        client = UORAddrClient()
        obj = client.wrap_with_uor({"key": "value"}, source="test")
        assert obj.digest is not None
        assert obj.digest.startswith("sha256:")
        assert any(p["source"] == "test" for p in obj.provenance)
        assert obj.schema_extensions.get("uor_addr_digest") == obj.digest

    def test_resolve_cached_digest(self):
        client = UORAddrClient()
        obj = client.wrap_with_uor({"cached": True})
        found = client.resolve(obj.digest)
        assert found is not None
        assert found.digest == obj.digest

    def test_resolve_missing_digest(self):
        client = UORAddrClient()
        assert client.resolve("sha256:nonexistent") is None


class TestHologramClient:
    def test_mock_query_when_no_key(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        client = HologramClient()
        assert not client.enabled
        result = client.query("test-model", {"x": 42})
        assert result["status"] == "mock"
        assert result["model_id"] == "test-model"

    def test_status_without_key(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        client = HologramClient()
        result = client.status()
        assert result["status"] == "mock"


class TestMoltbookClient:
    def test_list_topics_mock(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        monkeypatch.setenv("MOLTBOOK_API_KEY", "")
        client = MoltbookClient()
        result = client.list_topics()
        assert result["status"] == "mock"

    def test_search_mock(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        monkeypatch.setenv("MOLTBOOK_API_KEY", "")
        client = MoltbookClient()
        result = client.search("uor", limit=5)
        assert result["status"] == "mock"

    def test_post_without_key(self, monkeypatch):
        monkeypatch.setenv("MOLTBOOK_API_KEY", "")
        client = MoltbookClient()
        result = client.post_topic("Title", "Body")
        assert result["status"] == "error"
        assert "MOLTBOOK_API_KEY" in result["error"]


class TestPrismBTCClient:
    def test_anchor_placeholder(self):
        client = PrismBTCClient()
        result = client.anchor_digest("sha256:abc123")
        assert result["status"] == "placeholder"
        assert result["digest"] == "sha256:abc123"

    def test_verify_placeholder(self):
        client = PrismBTCClient()
        result = client.verify_anchor("sha256:abc123")
        assert result["status"] == "placeholder"


class TestSeveranceAIClient:
    def test_infer_placeholder(self):
        client = SeveranceAIClient()
        result = client.infer("hello", model="default")
        assert result["status"] == "placeholder"
        assert result["prompt"] == "hello"

    def test_verify_output_placeholder(self):
        client = SeveranceAIClient()
        result = client.verify_output("output", {"check": True})
        assert result["status"] == "placeholder"


class TestAnunixClient:
    def test_health_check_placeholder(self):
        client = AnunixClient()
        result = client.health_check("host-1")
        assert result["status"] == "placeholder"
        assert result["host_id"] == "host-1"

    def test_run_command_placeholder(self):
        client = AnunixClient()
        result = client.run_command("host-1", "uptime")
        assert result["status"] == "placeholder"
        assert result["command"] == "uptime"


class TestUOREcosystem:
    def test_status_returns_all_integrations(self):
        eco = UOREcosystem()
        status = eco.status()
        assert "uor_addr" in status
        assert "hologram" in status
        assert "moltbook" in status
        assert "prism_btc" in status
        assert "severance_ai" in status
        assert "anunix" in status

    def test_global_instance(self):
        reset_uor_ecosystem()
        eco1 = get_uor_ecosystem()
        eco2 = get_uor_ecosystem()
        assert eco1 is eco2
        reset_uor_ecosystem()
        eco3 = get_uor_ecosystem()
        assert eco3 is not eco1


class TestHTTPHelpers:
    def test_http_post_without_httpx(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        result = _http_post("http://example.com", {})
        assert result["status"] == "mock"

    def test_http_get_without_httpx(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        result = _http_get("http://example.com")
        assert result["status"] == "mock"


class TestSecurity:
    """SSRF and security hardening tests for ecosystem HTTP layer."""

    def test_is_url_safe_blocks_private_ip(self):
        from uar.core.uor_ecosystem import _is_url_safe

        assert _is_url_safe("http://localhost/test") is False
        assert _is_url_safe("http://127.0.0.1/test") is False
        assert _is_url_safe("http://10.0.0.1/test") is False
        assert _is_url_safe("http://192.168.1.1/test") is False
        assert _is_url_safe("http://172.16.0.1/test") is False
        assert _is_url_safe("http://169.254.1.1/test") is False
        assert _is_url_safe("http://0.0.0.0/test") is False

    def test_is_url_safe_allows_public_https(self):
        from uar.core.uor_ecosystem import _is_url_safe

        assert _is_url_safe("https://api.gethologram.ai/v1/infer") is True
        assert _is_url_safe("https://moltbook.com/api/v1/topics") is True
        assert _is_url_safe("http://example.com") is True

    def test_is_url_safe_blocks_non_http_schemes(self):
        from uar.core.uor_ecosystem import _is_url_safe

        assert _is_url_safe("file:///etc/passwd") is False
        assert _is_url_safe("ftp://example.com") is False
        assert _is_url_safe("ssh://example.com") is False
        assert _is_url_safe("data:text/html,test") is False

    def test_http_post_blocks_unsafe_url(self):
        from uar.core.uor_ecosystem import _http_post

        result = _http_post("http://localhost:8000/secret", {})
        assert result["status"] == "error"
        assert "Unsafe URL blocked" in result["error"]

    def test_http_get_blocks_unsafe_url(self):
        from uar.core.uor_ecosystem import _http_get

        result = _http_get("http://127.0.0.1:8000/secret")
        assert result["status"] == "error"
        assert "Unsafe URL blocked" in result["error"]


class TestUORFoundationClient:
    def test_verify_default_x(self):
        client = UORFoundationClient()
        assert client.base_url == os.getenv(
            "UOR_FOUNDATION_API_URL", "https://api.uor.foundation/v1"
        )
        assert client.enabled is True

    def test_status_mock_when_no_httpx(self, monkeypatch):
        monkeypatch.setattr(
            "uar.core.uor_ecosystem.HTTPX_AVAILABLE", False
        )
        client = UORFoundationClient()
        result = client.status()
        assert result["reachable"] is False
        assert "unconfigured" in result["status"]

    def test_foundation_url_blocked_by_ssrf(self):
        from uar.core.uor_ecosystem import _is_url_safe

        # The UOR Foundation API is a public endpoint — should be safe
        assert _is_url_safe(
            "https://api.uor.foundation/v1/kernel/op/verify?x=42"
        ) is True


class TestEcosystemStatusLive:
    def test_status_includes_foundation(self):
        eco = get_uor_ecosystem()
        result = eco.status()
        assert "uor_foundation" in result
        assert "reachable" in result["uor_foundation"]
        assert "ping" in result["uor_foundation"]

    def test_status_includes_hologram_reachability(self):
        eco = get_uor_ecosystem()
        result = eco.status()
        assert "hologram" in result
        assert "reachable" in result["hologram"]
