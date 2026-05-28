"""Tests for DNS resolution.

Covers ObjectLocation, UORDNSResolver, and related helpers.
"""

from unittest.mock import patch

from uar.uor.dns_resolution import (
    DNS_AVAILABLE,
    RecordType,
    ObjectLocation,
    UORDNSResolver,
)


class TestRecordType:
    """DNS record type enum."""

    def test_values(self):
        assert RecordType.TXT.value == "TXT"
        assert RecordType.SRV.value == "SRV"
        assert RecordType.A.value == "A"


class TestObjectLocation:
    """ObjectLocation dataclass."""

    def test_defaults(self):
        loc = ObjectLocation(hostname="example.com")
        assert loc.port is None
        assert loc.protocol == "http"
        assert loc.path is None
        assert loc.metadata is None

    def test_to_dict(self):
        loc = ObjectLocation(
            hostname="example.com",
            port=8080,
            protocol="https",
            path="/api/v1",
            metadata={"region": "us-east"},
        )
        d = loc.to_dict()
        assert d["hostname"] == "example.com"
        assert d["port"] == 8080
        assert d["protocol"] == "https"
        assert d["path"] == "/api/v1"
        assert d["metadata"] == {"region": "us-east"}

    def test_get_url_no_port_no_path(self):
        loc = ObjectLocation(hostname="example.com")
        assert loc.get_url() == "http://example.com"

    def test_get_url_with_port(self):
        loc = ObjectLocation(hostname="example.com", port=8080)
        assert loc.get_url() == "http://example.com:8080"

    def test_get_url_with_path(self):
        loc = ObjectLocation(
            hostname="example.com", port=443, path="/objects/1"
        )
        assert loc.get_url() == "http://example.com:443/objects/1"


class TestUORDNSResolverInit:
    """Resolver initialization."""

    def test_init_no_server(self):
        resolver = UORDNSResolver()
        assert resolver.dns_server is None
        assert resolver.cache == {}
        if DNS_AVAILABLE:
            assert resolver.resolver is not None

    def test_init_with_server(self):
        resolver = UORDNSResolver(dns_server="8.8.8.8")
        assert resolver.dns_server == "8.8.8.8"

    def test_init_no_dns_available(self):
        with patch("uar.uor.dns_resolution.DNS_AVAILABLE", False):
            resolver = UORDNSResolver()
            assert resolver.resolver is None


class TestUORDNSResolverCache:
    """Caching behavior."""

    def test_cache_hit(self):
        resolver = UORDNSResolver()
        loc = ObjectLocation(hostname="cached.example.com")
        resolver.cache["test.uor.local"] = loc
        result = resolver.resolve_object("test")
        assert result is not None
        assert result.hostname == "cached.example.com"


class TestUORDNSResolverNoDNS:
    """Behavior when dnspython unavailable."""

    def test_resolve_no_dns(self):
        with patch("uar.uor.dns_resolution.DNS_AVAILABLE", False):
            resolver = UORDNSResolver()
            result = resolver.resolve_object("test")
            assert result is None

    def test_resolve_service_no_dns(self):
        with patch("uar.uor.dns_resolution.DNS_AVAILABLE", False):
            resolver = UORDNSResolver()
            result = resolver.resolve_service("_http._tcp.example.com")
            assert result is None


class TestUORDNSResolverClearCache:
    """Cache management."""

    def test_clear_cache(self):
        resolver = UORDNSResolver()
        resolver.cache["test"] = ObjectLocation(hostname="a.com")
        resolver.clear_cache()
        assert resolver.cache == {}
