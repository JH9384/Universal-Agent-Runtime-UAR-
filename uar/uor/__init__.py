"""UOR compatibility layer for Universal Agent Runtime.

This module provides UOR-aligned functionality including:
- Bounded shape recursion for JSON processing
- Typed JSON value handling with case distinction
- Content-derived address computation
- Canonicalization with recursion bounds
"""

from .bounded_json import (
    JsonCase,
    JsonValue,
    canonicalize_json,
    compute_uor_digest,
    MAX_RECURSION_DEPTH,
    MAX_ARRAY_LENGTH,
    MAX_OBJECT_KEYS,
)

__all__ = [
    "JsonCase",
    "JsonValue",
    "canonicalize_json",
    "compute_uor_digest",
    "MAX_RECURSION_DEPTH",
    "MAX_ARRAY_LENGTH",
    "MAX_OBJECT_KEYS",
]
