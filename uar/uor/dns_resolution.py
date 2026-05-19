"""DNS-based location resolution for distributed UOR object graphs.

Provides DNS-based resolution for UOR object locations in distributed
environments, enabling location-independent object addressing and retrieval.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    logging.warning(
        "dnspython not available. Install with: pip install dnspython"
    )

logger = logging.getLogger(__name__)


class RecordType(Enum):
    """DNS record types for UOR objects."""

    TXT = "TXT"
    SRV = "SRV"
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"


@dataclass
class ObjectLocation:
    """Represents a resolved object location."""

    hostname: str
    port: Optional[int] = None
    protocol: str = "http"
    path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hostname": self.hostname,
            "port": self.port,
            "protocol": self.protocol,
            "path": self.path,
            "metadata": self.metadata or {},
        }

    def get_url(self) -> str:
        """Get full URL for the object location."""
        url = f"{self.protocol}://{self.hostname}"
        if self.port:
            url += f":{self.port}"
        if self.path:
            url += self.path
        return url


class UORDNSResolver:
    """DNS-based resolver for UOR object locations."""

    def __init__(self, dns_server: Optional[str] = None):
        """Initialize UOR DNS resolver.

        Args:
            dns_server: Optional custom DNS server address
        """
        self.dns_server = dns_server
        self.cache: Dict[str, ObjectLocation] = {}
        self.resolver: Optional[Any] = None

        if DNS_AVAILABLE:
            self.resolver = dns.resolver.Resolver()
            if dns_server:
                self.resolver.nameservers = [dns_server]
        else:
            logger.warning("DNS resolution not available")

    def resolve_object(
        self,
        digest: str,
        domain: str = "uor.local",
    ) -> Optional[ObjectLocation]:
        """Resolve object location by digest.

        Args:
            digest: UOR object digest
            domain: DNS domain to query (default uor.local)

        Returns:
            ObjectLocation if found, None otherwise
        """
        # Check cache first
        cache_key = f"{digest}.{domain}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not DNS_AVAILABLE:
            logger.warning("DNS resolution not available")
            return None

        try:
            # Query TXT record for object metadata
            txt_record = f"{digest}.{domain}"
            txt_result = self._query_dns(txt_record, RecordType.TXT)

            # Query SRV record for service location
            srv_record = f"_uor._tcp.{digest}.{domain}"
            srv_result = self._query_dns(srv_record, RecordType.SRV)

            location = self._parse_dns_results(txt_result, srv_result)

            if location:
                self.cache[cache_key] = location
                msg = f"Resolved object {digest} to {location.get_url()}"
                logger.info(msg)
                return location
            else:
                logger.warning(f"Could not resolve object {digest}")
                return None

        except Exception as e:
            logger.error(f"DNS resolution failed for {digest}: {e}")
            return None

    def _query_dns(
        self, record: str, record_type: RecordType
    ) -> Optional[Any]:
        """Query DNS record.

        Args:
            record: DNS record to query
            record_type: Type of DNS record

        Returns:
            DNS response data or None
        """
        if not self.resolver:
            return None

        try:
            answer = self.resolver.resolve(record, record_type.value)
            return answer
        except dns.resolver.NXDOMAIN:
            logger.debug(f"DNS record not found: {record}")
            return None
        except Exception as e:
            logger.error(f"DNS query failed for {record}: {e}")
            return None

    def _parse_dns_results(
        self, txt_result: Any, srv_result: Any
    ) -> Optional[ObjectLocation]:
        """Parse DNS results into ObjectLocation.

        Args:
            txt_result: TXT record result
            srv_result: SRV record result

        Returns:
            ObjectLocation or None
        """
        metadata = {}
        hostname = None
        port = None
        protocol = "http"
        path = None

        # Parse TXT record for metadata
        if txt_result:
            for item in txt_result:
                txt_data = item.to_text()
                # TXT records are returned as quoted strings
                if txt_data.startswith('"') and txt_data.endswith('"'):
                    txt_data = txt_data[1:-1]

                # Parse key=value pairs
                for pair in txt_data.split():
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        metadata[key] = value

        # Parse SRV record for location
        if srv_result:
            srv_item = srv_result[0]
            hostname = str(srv_item.target).rstrip(".")
            port = srv_item.port

        # Extract location info from metadata if SRV not available
        if not hostname and "hostname" in metadata:
            hostname = metadata["hostname"]
        if not port and "port" in metadata:
            port = int(metadata["port"])
        if "protocol" in metadata:
            protocol = metadata["protocol"]
        if "path" in metadata:
            path = metadata["path"]

        if hostname:
            return ObjectLocation(
                hostname=hostname,
                port=port,
                protocol=protocol,
                path=path,
                metadata=metadata,
            )
        else:
            return None

    def register_object(
        self,
        digest: str,
        location: ObjectLocation,
        domain: str = "uor.local",
    ) -> bool:
        """Register object location in DNS.

        Args:
            digest: UOR object digest
            location: Object location to register
            domain: DNS domain to use

        Returns:
            True if registered successfully, False otherwise

        Note:
            This is a placeholder for DNS update functionality.
            Actual DNS updates require proper authentication and
            dynamic DNS server configuration.
        """
        logger.warning(
            f"DNS registration not implemented for {digest} at {location.get_url()}"
        )
        logger.warning(
            "DNS registration requires dynamic DNS server configuration"
        )
        return False

    def resolve_service(
        self,
        service_name: str,
        domain: str = "uor.local",
    ) -> Optional[ObjectLocation]:
        """Resolve UOR service location.

        Args:
            service_name: Name of the service (e.g., "storage", "compute")
            domain: DNS domain to query

        Returns:
            ObjectLocation if found, None otherwise
        """
        cache_key = f"_service_{service_name}.{domain}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not DNS_AVAILABLE:
            logger.warning("DNS resolution not available")
            return None

        try:
            # Query SRV record for service
            srv_record = f"_uor-{service_name}._tcp.{domain}"
            srv_result = self._query_dns(srv_record, RecordType.SRV)

            if srv_result:
                srv_item = srv_result[0]
                location = ObjectLocation(
                    hostname=str(srv_item.target).rstrip("."),
                    port=srv_item.port,
                    protocol="http",
                )
                self.cache[cache_key] = location
                prefix = f"Resolved service {service_name} to"
                msg = f"{prefix} {location.get_url()}"
                logger.info(msg)
                return location
            else:
                logger.warning(f"Could not resolve service {service_name}")
                return None

        except Exception as e:
            logger.error(f"Service resolution failed for {service_name}: {e}")
            return None

    def clear_cache(self):
        """Clear DNS resolution cache."""
        self.cache.clear()
        logger.info("DNS resolution cache cleared")


class DistributedObjectGraph:
    """Manages distributed UOR object graphs with DNS resolution."""

    def __init__(self, dns_resolver: Optional[UORDNSResolver] = None):
        """Initialize distributed object graph.

        Args:
            dns_resolver: Optional custom DNS resolver
        """
        self.dns_resolver = dns_resolver or UORDNSResolver()
        self.local_objects: Dict[str, Any] = {}
        self.remote_locations: Dict[str, ObjectLocation] = {}

    def add_local_object(self, digest: str, object_data: Any):
        """Add object to local storage.

        Args:
            digest: UOR object digest
            object_data: Object data
        """
        self.local_objects[digest] = object_data
        msg = f"Added local object: {digest}"
        logger.info(msg)

    def get_object(self, digest: str, domain: str = "uor.local") -> Optional[Any]:
        """Get object, resolving location if needed.

        Args:
            digest: UOR object digest
            domain: DNS domain to query

        Returns:
            Object data if found, None otherwise
        """
        # Check local storage first
        if digest in self.local_objects:
            return self.local_objects[digest]

        # Resolve location via DNS
        location = self.dns_resolver.resolve_object(digest, domain)

        if location:
            self.remote_locations[digest] = location
            # In a real implementation, this would fetch the object
            # from the remote location
            logger.info(f"Object {digest} located at {location.get_url()}")
            return {"location": location.to_dict()}
        else:
            logger.warning(f"Could not locate object {digest}")
            return None

    def get_service_endpoint(
        self, service_name: str, domain: str = "uor.local"
    ) -> Optional[ObjectLocation]:
        """Get service endpoint via DNS.

        Args:
            service_name: Name of the service
            domain: DNS domain to query

        Returns:
            ObjectLocation if found, None otherwise
        """
        return self.dns_resolver.resolve_service(service_name, domain)

    def list_remote_objects(self) -> List[str]:
        """List objects with known remote locations.

        Returns:
            List of object digests
        """
        return list(self.remote_locations.keys())

    def list_local_objects(self) -> List[str]:
        """List objects in local storage.

        Returns:
            List of object digests
        """
        return list(self.local_objects.keys())


class DNSBasedLinkResolver:
    """Resolves UOR links using DNS-based location resolution."""

    def __init__(self, dns_resolver: Optional[UORDNSResolver] = None):
        """Initialize DNS-based link resolver.

        Args:
            dns_resolver: Optional custom DNS resolver
        """
        self.dns_resolver = dns_resolver or UORDNSResolver()
        self.graph = DistributedObjectGraph(self.dns_resolver)

    def resolve_link(
        self,
        target_digest: str,
        domain: str = "uor.local",
    ) -> Optional[ObjectLocation]:
        """Resolve link target to location.

        Args:
            target_digest: Target object digest
            domain: DNS domain to query

        Returns:
            ObjectLocation if found, None otherwise
        """
        return self.dns_resolver.resolve_object(target_digest, domain)

    def resolve_link_chain(
        self,
        digests: List[str],
        domain: str = "uor.local",
    ) -> List[Optional[ObjectLocation]]:
        """Resolve a chain of link targets.

        Args:
            digests: List of object digests to resolve
            domain: DNS domain to query

        Returns:
            List of ObjectLocations (None for unresolved)
        """
        locations = []
        for digest in digests:
            location = self.resolve_link(digest, domain)
            locations.append(location)
        return locations

    def get_link_statistics(self) -> Dict[str, Any]:
        """Get statistics about link resolution.

        Returns:
            Dictionary with resolution statistics
        """
        return {
            "remote_objects": len(self.graph.list_remote_objects()),
            "local_objects": len(self.graph.list_local_objects()),
            "cache_size": len(self.dns_resolver.cache),
        }
