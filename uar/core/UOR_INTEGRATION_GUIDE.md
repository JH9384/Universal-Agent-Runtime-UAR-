# UOR Integration Guide for UAR

This guide explains the Universal Object Runtime (UOR) integration layer for the Universal Agent Runtime (UAR) system.

## Overview

The UOR integration layer provides comprehensive object tracking, integrity verification, and provenance tracking throughout the UAR system. It is aligned with UOR Foundation standards including base attributes (size, mediaType, digest), schema extensions, and object modes.

## Core Components

### UORObject

The `UORObject` class wraps data with UOR tracking capabilities:

```python
from uar.core.uor_integration import UORObject, ObjectMode

# Create a UOR object
uor_obj = UORObject(
    data={"key": "value"},
    mode=ObjectMode.IMMUTABLE_SINGULAR
)

# Compute digest
digest = uor_obj.compute_digest()

# Add provenance
uor_obj.add_provenance(source="my_skill", operation="process")

# Add schema extensions
uor_obj.add_schema_extension("custom_field", "custom_value")

# Get base attributes (UOR Foundation standard)
base_attrs = uor_obj.get_base_attributes()
# Returns: {"size": 123, "mediaType": "application/json", "digest": "sha256:..."}
```

### Object Modes

UOR defines three object modes:

- **IMMUTABLE_SINGULAR**: Provides integrity through digest-based references
- **MUTABLE_SINGULAR**: Provides human-readable addressing schemes and dynamic content
- **MUTABLE_ARRAY**: Provides human-readable addressing with unknown object count

```python
from uar.core.uor_integration import ObjectMode

# Immutable object (default)
immutable_obj = UORObject(data="static content", mode=ObjectMode.IMMUTABLE_SINGULAR)

# Mutable object
mutable_obj = UORObject(data="dynamic content", mode=ObjectMode.MUTABLE_SINGULAR)

# Mutable array
array_obj = UORObject(data=["item1", "item2"], mode=ObjectMode.MUTABLE_ARRAY)
```

### UORIntegrator

The main coordinator for UOR operations:

```python
from uar.core.uor_integration import get_uor_integrator

integrator = get_uor_integrator()

# Wrap data with UOR
uor_obj = integrator.wrap_object(data, source="my_component")

# Apply transformations
transformed = integrator.apply_transformation(
    uor_obj,
    transformation_type="normalize",
    parameters={"method": "minmax"},
    transform_fn=lambda x, **kw: x
)

# Verify integrity
is_valid = uor_obj.verify_integrity(expected_digest)

# Get digest history
history = integrator.get_digest_history(source="my_component")
```

## Convenience Functions

```python
from uar.core.uor_integration import (
    wrap_input_data,
    wrap_output_data,
    verify_output_integrity,
)

# Wrap input data
input_uor = wrap_input_data(data, source="input")

# Wrap output data
output_uor = wrap_output_data(result, source="skill_output")

# Verify output integrity
is_valid = verify_output_integrity(output_uor, expected_digest)
```

## Integration Points

The UOR integration layer is used throughout the UAR system:

- **Executor**: Tracks skill inputs/outputs with digests and provenance
- **Orchestrator**: Adds UOR digests to orchestration nodes
- **Skill Registry**: Computes skill digests from source code
- **Cache Layer**: Stores and verifies UOR digests for cached results
- **Validation Layer**: Tracks validated goals
- **Guardrails**: Tracks policy violations with UOR digests
- **API Layer**: Wraps requests/responses with UOR objects
- **Memory Layer**: Stores UOR digests with persistent records

## Base Attributes (UOR Foundation Standard)

All UOR objects include three base attributes as defined by UOR Foundation:

1. **size**: Object size in bytes
2. **mediaType**: MIME type or content type (e.g., "application/json")
3. **digest**: SHA256 hash for integrity verification

```python
uor_obj = UORObject(data={"key": "value"})
base_attrs = uor_obj.get_base_attributes()
# {"size": 123, "mediaType": "application/json", "digest": "sha256:..."}
```

## Schema Extensions

Schema extensions allow adding custom attributes to UOR objects:

```python
uor_obj.add_schema_extension("custom_attr", "value")
uor_obj.add_schema_extension("tags", ["tag1", "tag2"])
```

## Provenance Tracking

Track the history of operations on UOR objects:

```python
uor_obj.add_provenance(source="skill_a", operation="execute")
uor_obj.add_provenance(source="skill_b", operation="transform")

# View provenance
for record in uor_obj.provenance:
    print(f"{record['source']}: {record['operation']}")
```

## Transformation Tracking

Track transformations applied to UOR objects:

```python
uor_obj.add_transformation(
    transformation_type="normalize",
    parameters={"method": "minmax"}
)
```

## Best Practices

1. **Always compute digests**: Call `compute_digest()` after creating or modifying data
2. **Track provenance**: Add provenance records for each operation
3. **Use appropriate object modes**: Choose the mode based on data mutability
4. **Add schema extensions**: Use schema extensions for custom metadata
5. **Verify integrity**: Verify digests when retrieving data from storage
6. **Cache UOR objects**: Use the integrator's cache to avoid recomputing digests

## Related Components

- **Sigmatics Integration**: Atlas Sigil Algebra for mathematical operations
- **Atlas Embeddings**: Golden Seed Vector for E8 Lie group embeddings
- **Ego Guard Forge**: Security policy enforcement
- **Prism**: Data transformation and refraction

## Troubleshooting

### Digest Mismatch

If you encounter digest mismatches:
- Ensure data is serialized consistently (use `sort_keys=True` in JSON dumps)
- Check that the digest algorithm matches (default is SHA256)
- Verify that the data hasn't been modified between digest computation and verification

### Memory Issues

If you encounter memory issues with large objects:
- Use the integrator's cache to avoid duplicate UOR objects
- Consider using MUTABLE_SINGULAR mode for large dynamic data
- Clear digest history periodically: `integrator.digest_history.clear()`

### Performance

For optimal performance:
- Batch operations when possible
- Use the global integrator instance instead of creating new ones
- Cache UOR objects that are frequently accessed
