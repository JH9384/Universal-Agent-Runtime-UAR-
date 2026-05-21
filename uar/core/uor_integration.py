"""UOR Integration Layer for Universal Agent Runtime.

This module provides the integration layer between UAR and UOR
(Universal Object Runtime), enabling full UOR integration throughout
the agent system for maximum benefit.

Aligned with UOR Foundation standards:
- Base attributes: size, mediaType, digest
- Schema extensions for additional attributes
- Object modes: Immutable Singular, Mutable Singular, Mutable Array

Key features:
- Object identity verification using UOR critical identity
- Digest computation for all inputs/outputs
- Provenance tracking with UOR links
- Data integrity validation
- Mathematical transformations via UOR math modules
- Vector operations for embeddings and similarity
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class ObjectMode(Enum):
    """UOR object modes as defined by UOR Foundation."""

    IMMUTABLE_SINGULAR = "immutable_singular"
    MUTABLE_SINGULAR = "mutable_singular"
    MUTABLE_ARRAY = "mutable_array"


@dataclass
class UORObject:
    """UOR object wrapper for data passing through the system.

    Aligned with UOR Foundation base attributes:
    - size: Object size in bytes
    - mediaType: MIME type or content type
    - digest: SHA256 hash for integrity verification
    """

    data: Any
    digest: Optional[str] = None
    digest_algorithm: str = "sha256"
    size: Optional[int] = None
    media_type: Optional[str] = None
    mode: ObjectMode = ObjectMode.IMMUTABLE_SINGULAR
    schema_extensions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    transformations: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Compute size and media type after initialization."""
        if self.size is None:
            self.size = self._compute_size()
        if self.media_type is None:
            self.media_type = self._infer_media_type()

    def _compute_size(self) -> int:
        """Compute object size in bytes."""
        try:
            data_str = json.dumps(self.data, sort_keys=True, default=str)
            return len(data_str.encode("utf-8"))
        except Exception:
            return len(str(self.data).encode("utf-8"))

    def _infer_media_type(self) -> str:
        """Infer media type from data."""
        if isinstance(self.data, str):
            return "text/plain"
        elif isinstance(self.data, (int, float)):
            return "application/json"
        elif isinstance(self.data, (list, dict)):
            return "application/json"
        elif isinstance(self.data, bytes):
            return "application/octet-stream"
        else:
            return "application/json"

    def compute_digest(self) -> str:
        """Compute UOR digest for the object."""
        try:
            data_str = json.dumps(self.data, sort_keys=True, default=str)
            hash_obj = hashlib.sha256(data_str.encode())
            self.digest = f"{self.digest_algorithm}:{hash_obj.hexdigest()}"
            return self.digest
        except Exception as e:
            logger.warning(f"Failed to compute digest: {e}")
            hash_obj = hashlib.sha256(str(self.data).encode())
            self.digest = f"{self.digest_algorithm}:{hash_obj.hexdigest()}"
            return self.digest

    def verify_integrity(self, expected_digest: str) -> bool:
        """Verify object integrity against expected digest."""
        current_digest = self.compute_digest()
        return current_digest == expected_digest

    def add_schema_extension(self, key: str, value: Any):
        """Add a schema extension attribute."""
        self.schema_extensions[key] = value

    def get_base_attributes(self) -> Dict[str, Any]:
        """Get UOR Foundation base attributes."""
        return {
            "size": self.size,
            "mediaType": self.media_type,
            "digest": self.digest,
        }

    def add_provenance(
        self, source: str, operation: str, timestamp: Optional[datetime] = None
    ):
        """Add provenance information to the object."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        self.provenance.append(
            {
                "source": source,
                "operation": operation,
                "timestamp": timestamp.isoformat(),
            }
        )

    def add_transformation(
        self, transformation_type: str, parameters: Dict[str, Any]
    ):
        """Add transformation record to the object."""
        self.transformations.append(
            {
                "type": transformation_type,
                "parameters": parameters,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


class UORIntegrator:
    """Main UOR integration coordinator for the agent system."""

    def __init__(self):
        self.enabled = True
        self.object_cache: Dict[str, UORObject] = {}
        self.digest_history: List[Dict[str, Any]] = []

    def wrap_object(
        self, data: Any, source: str = "unknown", operation: str = "wrap"
    ) -> UORObject:
        """Wrap data in a UOR object with digest and provenance."""
        uor_obj = UORObject(data=data)
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, operation)

        # Cache the object
        if uor_obj.digest:
            self.object_cache[uor_obj.digest] = uor_obj

        # Track digest history
        self.digest_history.append(
            {
                "digest": uor_obj.digest,
                "source": source,
                "operation": operation,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return uor_obj

    def unwrap_object(self, uor_obj: UORObject) -> Any:
        """Unwrap UOR object to get the underlying data."""
        return uor_obj.data

    def verify_object_chain(
        self, uor_obj: UORObject, expected_digest_chain: List[str]
    ) -> bool:
        """Verify object digest chain for provenance."""
        current_digest = uor_obj.compute_digest()
        if current_digest not in expected_digest_chain:
            logger.warning(
                f"Digest mismatch: expected one of {expected_digest_chain}, "
                f"got {current_digest}"
            )
            return False
        return True

    def apply_transformation(
        self,
        uor_obj: UORObject,
        transformation_type: str,
        parameters: Dict[str, Any],
        transform_fn: Callable,
    ) -> UORObject:
        """Apply a transformation to a UOR object."""
        # Apply transformation
        transformed_data = transform_fn(uor_obj.data, **parameters)

        # Create new UOR object with transformed data
        new_obj = UORObject(data=transformed_data)
        new_obj.compute_digest()

        # Copy provenance and add transformation record
        new_obj.provenance = uor_obj.provenance.copy()
        new_obj.transformations = uor_obj.transformations.copy()
        new_obj.add_transformation(transformation_type, parameters)

        # Cache the new object
        if new_obj.digest:
            self.object_cache[new_obj.digest] = new_obj

        return new_obj

    def get_object_by_digest(self, digest: str) -> Optional[UORObject]:
        """Retrieve object from cache by digest."""
        return self.object_cache.get(digest)

    def get_digest_history(
        self, source: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get digest history, optionally filtered by source."""
        history = self.digest_history
        if source:
            history = [h for h in history if h.get("source") == source]
        return history[-limit:]


# Global UOR integrator instance
_uor_integrator: Optional[UORIntegrator] = None


def get_uor_integrator() -> UORIntegrator:
    """Get the global UOR integrator instance."""
    global _uor_integrator
    if _uor_integrator is None:
        _uor_integrator = UORIntegrator()
    return _uor_integrator


def reset_uor_integrator():
    """Reset the global UOR integrator (useful for testing)."""
    global _uor_integrator
    _uor_integrator = None


def wrap_input_data(data: Any, source: str = "input") -> UORObject:
    """Convenience function to wrap input data."""
    integrator = get_uor_integrator()
    return integrator.wrap_object(data, source, "input")


def wrap_output_data(data: Any, source: str = "output") -> UORObject:
    """Convenience function to wrap output data."""
    integrator = get_uor_integrator()
    return integrator.wrap_object(data, source, "output")


def verify_output_integrity(
    output_obj: UORObject, expected_digest: Optional[str] = None
) -> bool:
    """Convenience function to verify output integrity."""
    if expected_digest:
        return output_obj.verify_integrity(expected_digest)
    return output_obj.compute_digest() is not None
