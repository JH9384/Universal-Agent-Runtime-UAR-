"""Tests for UOR Ecosystem integration layer."""

from uar.core.uor_ecosystem import (
    UORAddrClient,
    HologramClient,
    MoltbookClient,
    PrismBTCClient,
    SeveranceAIClient,
    AnunixClient,
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
