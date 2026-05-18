# UOR Implementation Usage Guide

This guide explains how to use the UOR (Universal Object Reference) implementation in UAR for content-derived addressing and canonical JSON processing.

## Overview

The UOR implementation (`uar.uor.bounded_json`) provides:
- **Typed JSON value handling** with case distinction (CT-T)
- **Bounded recursion** to prevent DoS attacks (CT-B)
- **JCS-RFC8785 canonicalization** for standard compliance
- **Unicode NFC normalization** for consistent string representation
- **Content-derived addressing** via SHA-256 digests

## Basic Usage

### Converting Python Objects to UOR

```python
from uar.uor import JsonValue, compute_uor_digest, canonicalize_json

# Simple object
obj = {"name": "Alice", "age": 30, "active": True}

# Convert to typed JsonValue
json_value = JsonValue.from_python(obj)

# Get canonical bytes
canonical_bytes = json_value.to_canonical_bytes()

# Get content-derived address (digest)
digest = json_value.compute_digest()
# Returns: "sha256:<hex-digest>"
```

### Computing Digests Directly

```python
from uar.uor import compute_uor_digest

obj = {"key": "value"}
digest = compute_uor_digest(obj)
# digest = "sha256:abc123..."
```

### Canonicalizing JSON

```python
from uar.uor import canonicalize_json

obj = {"z": 3, "a": 1, "m": 2}
canonical = canonicalize_json(obj)
# Returns canonical JSON string with sorted keys
```

## Case Distinction (CT-T)

UOR treats semantically distinct JSON values as distinct:

```python
from uar.uor import JsonValue

# Number vs string (different digests)
num = JsonValue.from_python(42)
str_val = JsonValue.from_python("42")
assert num.compute_digest() != str_val.compute_digest()

# Boolean values (pairwise distinct)
null = JsonValue.from_python(None)
false = JsonValue.from_python(False)
true = JsonValue.from_python(True)
assert null.compute_digest() != false.compute_digest()
assert false.compute_digest() != true.compute_digest()
```

## Bounded Recursion (CT-B)

The implementation enforces limits to prevent DoS:

- **MAX_RECURSION_DEPTH**: 1000 levels
- **MAX_ARRAY_LENGTH**: 10,000 elements
- **MAX_OBJECT_KEYS**: 10,000 keys

```python
from uar.uor import JsonValue, MAX_ARRAY_LENGTH

# This will raise ValueError
large_array = list(range(MAX_ARRAY_LENGTH + 1))
json_value = JsonValue.from_python(large_array)  # Raises

# This will succeed
exact_array = list(range(MAX_ARRAY_LENGTH))
json_value = JsonValue.from_python(exact_array)  # OK
```

## Customizing Limits

If you need different limits, modify the constants before importing:

```python
import uar.uor.bounded_json as uor_json

# Increase limits for your use case
uor_json.MAX_RECURSION_DEPTH = 2000
uor_json.MAX_ARRAY_LENGTH = 20000
uor_json.MAX_OBJECT_KEYS = 20000

from uar.uor import JsonValue
```

## Unicode Normalization

The implementation applies Unicode NFC normalization to ensure consistent string representation:

```python
from uar.uor import JsonValue

# Different Unicode representations normalize to same digest
obj1 = {"text": "café"}  # Combined é
obj2 = {"text": "cafe\u0301"}  # Decomposed e + combining acute

json_value1 = JsonValue.from_python(obj1)
json_value2 = JsonValue.from_python(obj2)

assert json_value1.compute_digest() == json_value2.compute_digest()
```

## Round-Trip Conversion

Convert Python → JsonValue → Python:

```python
from uar.uor import JsonValue

original = {
    "null": None,
    "bool": True,
    "number": 42,
    "string": "hello",
    "array": [1, 2, 3],
    "object": {"nested": "value"}
}

json_value = JsonValue.from_python(original)
recovered = json_value.to_python()

assert recovered == original
```

## Error Handling

The implementation provides detailed error messages:

```python
from uar.uor import JsonValue

try:
    # Exceeds array length limit
    large = list(range(15000))
    JsonValue.from_python(large)
except ValueError as e:
    # Error message includes actual value and limit
    # "Array length 15000 exceeds maximum of 10000.
    #  Reduce array size or increase MAX_ARRAY_LENGTH."
    print(e)
```

## Integration with UAR

The UOR implementation is used internally by UAR for:
- Object envelope addressing
- Content-derived identity
- Canonical representation for storage and comparison

### Example: Creating UOR-Aligned Envelopes

```python
from uar.uor import compute_uor_digest

content = {"data": "important information"}
digest = compute_uor_digest(content)

envelope = {
    "digest": digest,
    "mediaType": "application/json",
    "attributes": {},
    "links": [],
    "content": content
}
```

## Performance Considerations

- **Canonicalization**: O(n) where n is the size of the object
- **Digest computation**: O(n) plus SHA-256 hashing
- **Memory**: Proportional to object size (bounded by limits)
- **Thread-safe**: The implementation is stateless and thread-safe

## Testing

See `tests/test_uor_bridge.py` for comprehensive tests covering:
- Case distinction
- Bounded recursion enforcement
- Canonicalization idempotence
- Unicode normalization
- Round-trip conversion
- Real-world JSON structures

## Compliance

This implementation aligns with:
- **UOR-ADDR-1**: Bounded shape recursion specification
- **JCS-RFC8785**: JSON Canonicalization Scheme
- **UOR Foundation**: Native Python implementation of Rust specification

Note: No official Python `uor-addr` package exists on PyPI; this is a native implementation aligned with the UOR Foundation's Rust specification.
