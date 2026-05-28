"""Tests for DNS resolution.

Covers ObjectLocation, UORDNSResolver, and related helpers.
"""

from unittest.mock import MagicMock, patch

from uar.uor.dns_resolution import (
    DNS_AVAILABLE,
    RecordType,
    ObjectLocation,
    UORDNSResolver,
    DistributedObjectGraph,
    DNSBasedLinkResolver,
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


class TestUORDNSResolverQueryDNS:
    """_query_dns with mocked resolver."""

    def test_query_no_resolver(self):
        resolver = UORDNSResolver()
        resolver.resolver = None
        result = resolver._query_dns("test.com", RecordType.A)
        assert result is None

    def test_query_nxdomain(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        import dns.resolver

        with patch.object(
            resolver.resolver, "resolve", side_effect=dns.resolver.NXDOMAIN
        ):
            result = resolver._query_dns("test.com", RecordType.A)
        assert result is None

    def test_query_exception(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        with patch.object(
            resolver.resolver, "resolve", side_effect=Exception("fail")
        ):
            result = resolver._query_dns("test.com", RecordType.A)
        assert result is None

    def test_query_success(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        mock_answer = MagicMock()
        with patch.object(
            resolver.resolver, "resolve", return_value=mock_answer
        ):
            result = resolver._query_dns("test.com", RecordType.A)
        assert result is mock_answer


class TestUORDNSResolverParseDNS:
    """_parse_dns_results."""

    def test_parse_txt_only(self):
        resolver = UORDNSResolver()
        txt_item = MagicMock()
        txt_item.to_text.return_value = '"hostname=host1 port=8080 protocol=https path=/api"'  # noqa: E501
        txt_result = [txt_item]
        result = resolver._parse_dns_results(txt_result, None)
        assert result.hostname == "host1"
        assert result.port == 8080
        assert result.protocol == "https"
        assert result.path == "/api"

    def test_parse_srv_only(self):
        resolver = UORDNSResolver()
        srv_item = MagicMock()
        srv_item.target = "host1.example.com."
        srv_item.port = 9090
        srv_result = [srv_item]
        result = resolver._parse_dns_results(None, srv_result)
        assert result.hostname == "host1.example.com"
        assert result.port == 9090

    def test_parse_both(self):
        resolver = UORDNSResolver()
        txt_item = MagicMock()
        txt_item.to_text.return_value = '"protocol=https path=/obj"'
        srv_item = MagicMock()
        srv_item.target = "host1.example.com."
        srv_item.port = 9090
        result = resolver._parse_dns_results([txt_item], [srv_item])
        assert result.hostname == "host1.example.com"
        assert result.port == 9090
        assert result.protocol == "https"
        assert result.path == "/obj"

    def test_parse_no_hostname(self):
        resolver = UORDNSResolver()
        result = resolver._parse_dns_results(None, None)
        assert result is None

    def test_parse_unquoted_txt(self):
        resolver = UORDNSResolver()
        txt_item = MagicMock()
        txt_item.to_text.return_value = "hostname=host1"
        result = resolver._parse_dns_results([txt_item], None)
        assert result.hostname == "host1"


class TestUORDNSResolverResolveObject:
    """resolve_object with mocked DNS."""

    def test_resolve_object_full(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        txt_item = MagicMock()
        txt_item.to_text.return_value = '"protocol=https"'
        srv_item = MagicMock()
        srv_item.target = "host1.example.com."
        srv_item.port = 8080
        with patch.object(
            resolver.resolver, "resolve", side_effect=[
                [txt_item],  # TXT
                [srv_item],  # SRV
            ]
        ):
            result = resolver.resolve_object("abc123")
        assert result.hostname == "host1.example.com"
        assert result.port == 8080
        assert result.protocol == "https"

    def test_resolve_object_exception(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        with patch.object(
            resolver.resolver, "resolve", side_effect=Exception("fail")
        ):
            result = resolver.resolve_object("abc123")
        assert result is None


class TestUORDNSResolverResolveService:
    """resolve_service with mocked DNS."""

    def test_resolve_service_success(self):
        if not DNS_AVAILABLE:
            return
        resolver = UORDNSResolver()
        srv_item = MagicMock()
        srv_item.target = "storage.example.com."
        srv_item.port = 8080
        with patch.object(
            resolver.resolver, "resolve", return_value=[srv_item]
        ):
            result = resolver.resolve_service("storage")
        assert result.hostname == "storage.example.com"
        assert result.port == 8080

    def test_resolve_service_cache(self):
        resolver = UORDNSResolver()
        loc = ObjectLocation(hostname="cached.storage.com")
        resolver.cache["_service_storage.uor.local"] = loc
        result = resolver.resolve_service("storage")
        assert result.hostname == "cached.storage.com"

    def test_resolve_service_no_dns(self):
        with patch("uar.uor.dns_resolution.DNS_AVAILABLE", False):
            resolver = UORDNSResolver()
            result = resolver.resolve_service("storage")
        assert result is None


class TestUORDNSResolverRegister:
    """register_object placeholder."""

    def test_returns_false(self):
        resolver = UORDNSResolver()
        loc = ObjectLocation(hostname="example.com")
        result = resolver.register_object("abc", loc)
        assert result is False


class TestDistributedObjectGraph:
    """DistributedObjectGraph."""

    def test_add_local_object(self):
        graph = DistributedObjectGraph()
        graph.add_local_object("abc", {"data": "test"})
        assert "abc" in graph.local_objects

    def test_get_object_local(self):
        graph = DistributedObjectGraph()
        graph.add_local_object("abc", {"data": "test"})
        result = graph.get_object("abc")
        assert result == {"data": "test"}

    def test_get_object_remote(self):
        graph = DistributedObjectGraph()
        with patch.object(
            graph.dns_resolver, "resolve_object",
            return_value=ObjectLocation(hostname="remote.com"),
        ):
            result = graph.get_object("abc")
        assert result["location"]["hostname"] == "remote.com"

    def test_get_object_not_found(self):
        graph = DistributedObjectGraph()
        with patch.object(
            graph.dns_resolver, "resolve_object", return_value=None
        ):
            result = graph.get_object("abc")
        assert result is None

    def test_get_service_endpoint(self):
        graph = DistributedObjectGraph()
        with patch.object(
            graph.dns_resolver, "resolve_service",
            return_value=ObjectLocation(hostname="svc.com"),
        ):
            result = graph.get_service_endpoint("storage")
        assert result.hostname == "svc.com"

    def test_list_remote_objects(self):
        graph = DistributedObjectGraph()
        graph.remote_locations["abc"] = ObjectLocation(hostname="a.com")
        assert graph.list_remote_objects() == ["abc"]

    def test_list_local_objects(self):
        graph = DistributedObjectGraph()
        graph.add_local_object("abc", {"data": "test"})
        assert graph.list_local_objects() == ["abc"]


class TestDNSBasedLinkResolver:
    """DNSBasedLinkResolver."""

    def test_resolve_link(self):
        resolver = DNSBasedLinkResolver()
        with patch.object(
            resolver.dns_resolver, "resolve_object",
            return_value=ObjectLocation(hostname="target.com"),
        ):
            result = resolver.resolve_link("abc")
        assert result.hostname == "target.com"

    def test_resolve_link_chain(self):
        resolver = DNSBasedLinkResolver()
        with patch.object(
            resolver.dns_resolver, "resolve_object",
            return_value=ObjectLocation(hostname="target.com"),
        ):
            results = resolver.resolve_link_chain(["a", "b"])
        assert len(results) == 2
        assert results[0].hostname == "target.com"

    def test_get_link_statistics(self):
        resolver = DNSBasedLinkResolver()
        resolver.graph.add_local_object("abc", {})
        resolver.graph.remote_locations["def"] = ObjectLocation(
            hostname="a.com"
        )
        resolver.dns_resolver.cache["ghi"] = ObjectLocation(hostname="b.com")
        stats = resolver.get_link_statistics()
        assert stats["local_objects"] == 1
        assert stats["remote_objects"] == 1
        assert stats["cache_size"] == 1
