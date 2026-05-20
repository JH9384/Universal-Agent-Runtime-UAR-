"""UOR-aligned bounded JSON value processing with shape recursion limits.

Implements typed JSON value handling with case distinction (CT-T)
and bounded recursion depth enforcement (CT-B) as per UOR-ADDR-1.
Uses JCS-RFC8785 canonicalization with Unicode NFC normalization.
"""

import unicodedata
import rfc8785
import logging
from typing import Any
from enum import IntEnum
import hashlib

# Recursion depth limits to prevent stack overflow
MAX_RECURSION_DEPTH = 1000
MAX_ARRAY_LENGTH = 10000
MAX_OBJECT_KEYS = 10000

logger = logging.getLogger(__name__)


class JsonCase(IntEnum):
    """Typed JSON case tags for case distinction (CT-T)."""

    NULL = 0
    FALSE = 1
    TRUE = 2
    NUMBER = 3
    STRING = 4
    ARRAY = 5
    OBJECT = 6


class JsonValue:
    """Typed JSON value with case tag for UOR alignment.

    Implements CT-T: case distinction ensures that semantically distinct
    JSON values (e.g., 42 vs "42", null vs false vs true) produce distinct
    canonical forms.
    """

    def __init__(self, value: Any, case: JsonCase):
        self.value = value
        self.case = case

    @classmethod
    def from_python(cls, obj: Any, depth: int = 0) -> "JsonValue":
        """Convert Python object to typed JsonValue with recursion bounds
        (CT-B)."""
        if depth > MAX_RECURSION_DEPTH:
            msg = (
                f"Recursion depth {depth} exceeds maximum of {MAX_RECURSION_DEPTH}. "
                "Reduce nesting depth or increase MAX_RECURSION_DEPTH."
            )
            raise RecursionError(msg)

        if obj is None:
            return cls(obj, JsonCase.NULL)
        elif obj is False:
            return cls(obj, JsonCase.FALSE)
        elif obj is True:
            return cls(obj, JsonCase.TRUE)
        elif isinstance(obj, (int, float)):
            return cls(obj, JsonCase.NUMBER)
        elif isinstance(obj, str):
            return cls(obj, JsonCase.STRING)
        elif isinstance(obj, list):
            if len(obj) > MAX_ARRAY_LENGTH:
                msg = (
                    f"Array length {len(obj)} exceeds maximum of {MAX_ARRAY_LENGTH}. "
                    "Reduce array size or increase MAX_ARRAY_LENGTH."
                )
                raise ValueError(msg)
            return cls(
                [cls.from_python(item, depth + 1) for item in obj],
                JsonCase.ARRAY,
            )
        elif isinstance(obj, dict):
            if len(obj) > MAX_OBJECT_KEYS:
                msg = (
                    f"Object key count {len(obj)} exceeds maximum of {MAX_OBJECT_KEYS}. "
                    "Reduce number of keys or increase MAX_OBJECT_KEYS."
                )
                raise ValueError(msg)
            # Sort keys for canonical ordering
            sorted_obj = dict(sorted(obj.items()))
            return cls(
                {
                    k: cls.from_python(v, depth + 1)
                    for k, v in sorted_obj.items()
                },
                JsonCase.OBJECT,
            )
        else:
            raise TypeError(
                f"Unsupported type {type(obj).__name__} for JsonValue. "
                f"Supported types: None, bool, int, float, str, list, dict."
            )

    def to_canonical_bytes(self, depth: int = 0) -> bytes:
        """Generate canonical bytes representation with case tag prefix.

        Implements in-surface canonicalization where the case tag byte
        is included in the serialization, ensuring case distinction.
        Uses JCS-RFC8785 with Unicode NFC normalization
        per UOR-ADDR-1.
        """
        if depth > MAX_RECURSION_DEPTH:
            raise RecursionError(
                f"Recursion depth {depth} exceeds maximum of {MAX_RECURSION_DEPTH}. "
                "Reduce nesting depth or increase MAX_RECURSION_DEPTH."
            )

        # Convert to Python object for JCS canonicalization
        python_obj = self.to_python(depth)

        # Apply Unicode NFC normalization to strings
        normalized_obj = self._apply_nfc_normalization(python_obj)

        # Use JCS-RFC8785 canonicalization
        try:
            canonical = rfc8785.dumps(normalized_obj)
        except Exception as e:
            msg = (
                f"JCS canonicalization failed: {e}. "
                "Ensure the object contains only JSON-serializable types."
            )
            raise ValueError(msg) from e

        # Add case tag prefix for UOR case distinction (CT-T)
        case_byte = bytes([self.case.value])
        canonical_bytes = (
            canonical if isinstance(canonical, bytes)
            else canonical.encode("utf-8")
        )
        return case_byte + canonical_bytes

    def _apply_nfc_normalization(self, obj: Any, depth: int = 0) -> Any:
        """Apply Unicode NFC normalization to all strings including dictionary keys."""
        if depth > MAX_RECURSION_DEPTH:
            raise RecursionError(
                f"Recursion depth {depth} exceeds maximum of {MAX_RECURSION_DEPTH}. "
                "Reduce nesting depth or increase MAX_RECURSION_DEPTH."
            )

        if isinstance(obj, str):
            return unicodedata.normalize("NFC", obj)
        elif isinstance(obj, list):
            return [
                self._apply_nfc_normalization(item, depth + 1) for item in obj
            ]
        elif isinstance(obj, dict):
            return {
                unicodedata.normalize("NFC", k):
                self._apply_nfc_normalization(v, depth + 1)
                for k, v in obj.items()
            }
        else:
            return obj

    def compute_digest(self, algorithm: str = "sha256") -> str:
        """Compute digest of canonical bytes with specified algorithm.

        Args:
            algorithm: Hash algorithm to use (sha256, sha3_256, blake3)

        Returns:
            Digest string in format "<algorithm>:<hex>"
        """
        canonical = self.to_canonical_bytes()

        if algorithm == "sha256":
            return "sha256:" + hashlib.sha256(canonical).hexdigest()
        elif algorithm == "sha3_256":
            return "sha3_256:" + hashlib.sha3_256(canonical).hexdigest()
        elif algorithm == "blake3":
            try:
                import blake3  # type: ignore
                return "blake3:" + blake3.blake3(canonical).hexdigest()
            except ImportError:
                logger.warning(
                    "blake3 not available. Install with: pip install blake3"
                )
                # Fallback to SHA-256
                return "sha256:" + hashlib.sha256(canonical).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    def to_python(self, depth: int = 0) -> Any:
        """Convert back to Python object with recursion bounds."""
        if depth > MAX_RECURSION_DEPTH:
            raise RecursionError(
                f"Recursion depth {depth} exceeds maximum of {MAX_RECURSION_DEPTH}. "
                "Reduce nesting depth or increase MAX_RECURSION_DEPTH."
            )

        if self.case in (
            JsonCase.NULL,
            JsonCase.FALSE,
            JsonCase.TRUE,
            JsonCase.NUMBER,
            JsonCase.STRING,
        ):
            return self.value
        elif self.case == JsonCase.ARRAY:
            return [item.to_python(depth + 1) for item in self.value]
        elif self.case == JsonCase.OBJECT:
            return {k: v.to_python(depth + 1) for k, v in self.value.items()}
        else:
            raise ValueError(f"Unknown JsonCase: {self.case}")


def canonicalize_json(obj: Any) -> str:
    """Canonicalize JSON object with bounded recursion and case distinction.

    This is the in-surface canonicalization function that replaces
    the legacy jcs_nfc approach. It includes case tags in the
    canonical form to ensure CT-T case distinction.

    Args:
        obj: Python object to canonicalize

    Returns:
        Canonical JSON string with case tags embedded

    Raises:
        RecursionError: If recursion depth exceeds MAX_RECURSION_DEPTH
        ValueError: If array length or object key count exceeds limits
        TypeError: If unsupported type encountered
        UnicodeDecodeError: If canonical bytes cannot be decoded as UTF-8
    """
    json_value = JsonValue.from_python(obj)
    canonical_bytes = json_value.to_canonical_bytes()
    # Use strict decoding to prevent silent data corruption
    return canonical_bytes.decode("utf-8", errors="strict")


def compute_uor_digest(obj: Any, algorithm: str = "sha256") -> str:
    """Compute UOR content-derived address with specified algorithm.

    Args:
        obj: Python object to digest
        algorithm: Hash algorithm to use (sha256, sha3_256, blake3)

    Returns:
        UOR digest string in format "<algorithm>:<hex>"
    """
    json_value = JsonValue.from_python(obj)
    return json_value.compute_digest(algorithm)
