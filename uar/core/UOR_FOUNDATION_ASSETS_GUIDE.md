# UOR Foundation Assets Integration Guide

This guide explains the UOR Foundation assets integrated into the UAR system.

## Overview

The UAR system now includes integration layers for all major UOR Foundation assets, providing mathematical operations, security, and data transformation capabilities.

## Integrated Assets

### 1. Sigmatics (Atlas Sigil Algebra)

**File**: `uar/core/sigmatics_integration.py`

Sigmatics provides the Atlas Sigil Algebra reference implementation for mathematical operations.

#### Usage

```python
from uar.core.sigmatics_integration import (
    create_sigil,
    create_sigil_expression,
    get_sigmatics_integrator,
)

# Create sigils
sigil1 = create_sigil("A", value=10)
sigil2 = create_sigil("B", value=20)

# Create expression
expr = create_sigil_expression([sigil1, sigil2], operation="sum")

# Evaluate
result = expr.evaluate()  # Returns 30

# Wrap with UOR
uor_obj = expr.wrap_with_uor(source="sigmatics")
```

#### Key Components

- **Sigil**: Represents a symbol in the Atlas Sigil Algebra
- **SigilExpression**: Represents a sigil expression/computation
- **SigmaticsIntegrator**: Main coordinator for sigil operations

#### Operations

- `sum`: Sum of sigil values
- `product`: Product of sigil values
- Custom operations can be added

#### CLI Integration

The SigmaticsIntegrator can optionally use the Sigmatics CLI if installed:

```python
integrator = get_sigmatics_integrator(use_cli=True)
```

### 2. Atlas Embeddings (Golden Seed Vector)

**File**: `uar/core/atlas_embeddings.py`

Atlas Embeddings provides the Golden Seed Vector for E8 Lie group embeddings, representing a universal mathematical language for describing symmetry and structure.

#### Usage

```python
from uar.core.atlas_embeddings import (
    create_golden_seed,
    get_atlas_integrator,
)

# Create Golden Seed Vector (248 dimensions for E8)
seed = create_golden_seed(dimensions=248, random=True)

# Compute symmetry properties
symmetry = seed.compute_symmetry()
# Returns: {"mean": 0.0, "std": 1.0, "norm": 1.0, "entropy": ...}

# Normalize
seed.normalize()

# Wrap with UOR
uor_obj = seed.wrap_with_uor(source="atlas_embeddings")
```

#### Key Components

- **GoldenSeedVector**: Represents the Golden Seed Vector (248 dimensions for E8)
- **AtlasEmbeddingsIntegrator**: Main coordinator for embedding operations

#### Operations

- `generate_random_seed`: Generate random vector
- `normalize`: Normalize to unit length
- `compute_similarity`: Cosine or Euclidean similarity
- `transform_vector`: Apply transformation matrix
- `batch_process_embeddings`: Process multiple data items

#### Similarity Methods

- `cosine`: Cosine similarity
- `euclidean`: Euclidean distance (converted to similarity)

### 3. Ego Guard Forge

**File**: `uar/core/ego_guard_forge.py`

Ego Guard Forge provides security policy enforcement and guardrail validation.

#### Usage

```python
from uar.core.ego_guard_forge import (
    create_security_policy,
    get_ego_guard_integrator,
)

# Create security policy
policy = create_security_policy(
    policy_id="policy_1",
    name="Data Access Policy",
    description="Controls data access",
    rules={"access_level": "admin"}
)

# Evaluate policy against context
context = {"access_level": "admin"}
result = policy.evaluate(context)  # Returns True

# Wrap with UOR
uor_obj = policy.wrap_with_uor(source="ego_guard")
```

#### Key Components

- **SecurityPolicy**: Represents a security policy with rules
- **EgoGuardForgeIntegrator**: Main coordinator for security operations

#### Features

- Policy evaluation against context
- Audit trail for security events
- Multiple policy support
- Integration with UOR for tracking

#### Audit Trail

```python
integrator = get_ego_guard_integrator()
audit_trail = integrator.get_audit_trail(limit=100)
```

### 4. Prism

**File**: `uar/core/prism_integration.py`

Prism provides data transformation and refraction capabilities through multiple facets.

#### Usage

```python
from uar.core.prism_integration import (
    create_prism,
    PrismFacet,
    get_prism_integrator,
)

# Create facets
facet1 = PrismFacet(facet_id="f1", name="uppercase", data="hello")
facet2 = PrismFacet(facet_id="f2", name="lowercase", data="world")

# Create prism
prism = create_prism(prism_id="prism_1", facets=[facet1, facet2])

# Refract data through facets
results = prism.refract("test data")

# Each result is a UOR object
for uor_obj in results:
    print(uor_obj.data)
```

#### Key Components

- **PrismFacet**: Represents a facet in the prism
- **Prism**: Represents a prism that refracts data into multiple facets
- **PrismIntegrator**: Main coordinator for prism operations

#### Operations

- `transform`: Apply transformation to facet data (uppercase, lowercase)
- `refract`: Refract data through all facets
- `add_facet`: Add a facet to the prism
- `get_facet`: Get a facet by ID

## Helper Utilities

### Global Integrator Instances

Each integration layer provides a global integrator instance:

```python
# UOR Integration
from uar.core.uor_integration import get_uor_integrator
uor_int = get_uor_integrator()

# Sigmatics
from uar.core.sigmatics_integration import get_sigmatics_integrator
sig_int = get_sigmatics_integrator()

# Atlas Embeddings
from uar.core.atlas_embeddings import get_atlas_integrator
atlas_int = get_atlas_integrator()

# Ego Guard Forge
from uar.core.ego_guard_forge import get_ego_guard_integrator
guard_int = get_ego_guard_integrator()

# Prism
from uar.core.prism_integration import get_prism_integrator
prism_int = get_prism_integrator()
```

### Reset Integrators (Testing)

```python
from uar.core.uor_integration import reset_uor_integrator
from uar.core.sigmatics_integration import reset_sigmatics_integrator
from uar.core.atlas_embeddings import reset_atlas_integrator
from uar.core.ego_guard_forge import reset_ego_guard_integrator
from uar.core.prism_integration import reset_prism_integrator

# Reset all integrators
reset_uor_integrator()
reset_sigmatics_integrator()
reset_atlas_integrator()
reset_ego_guard_integrator()
reset_prism_integrator()
```

## Integration with UOR System

All UOR Foundation assets are integrated with the UOR system:

- **Digest Tracking**: All operations generate UOR digests
- **Provenance**: Source and operation tracking
- **Schema Extensions**: Custom metadata via schema extensions
- **Object Modes**: Immutable/Mutable/Array support

## Example Workflow

```python
from uar.core.uor_integration import wrap_input_data, ObjectMode
from uar.core.sigmatics_integration import create_sigil_expression
from uar.core.atlas_embeddings import create_golden_seed
from uar.core.ego_guard_forge import create_security_policy
from uar.core.prism_integration import create_prism, PrismFacet

# Wrap input data with UOR
input_uor = wrap_input_data({"data": "test"}, source="workflow")

# Use Sigmatics for calculations
sigil_expr = create_sigil_expression(
    [create_sigil("A", value=5), create_sigil("B", value=10)],
    operation="sum"
)
result = sigil_expr.evaluate()

# Use Atlas Embeddings for vector operations
seed = create_golden_seed(dimensions=248, random=True)
symmetry = seed.compute_symmetry()

# Use Ego Guard Forge for security
policy = create_security_policy(
    policy_id="check_1",
    name="Input Validation",
    description="Validate input data",
    rules={"max_size": 1000}
)
is_valid = policy.evaluate({"max_size": 1000})

# Use Prism for data transformation
prism = create_prism(
    prism_id="transform_1",
    facets=[PrismFacet("f1", "upper", "data")]
)
transformed = prism.refract("test data")
```

## Best Practices

1. **Use global integrators**: Prefer global instances over creating new ones
2. **Wrap with UOR**: Always wrap results with UOR for tracking
3. **Reset in tests**: Reset integrators between test runs
4. **Check CLI availability**: For Sigmatics, check CLI availability before use
5. **Handle None values**: Handle optional vector data appropriately
6. **Audit security**: Review audit trails from ego-guard-forge regularly

## Troubleshooting

### Sigmatics CLI Not Available

If the Sigmatics CLI is not available, the Python-native implementation will be used automatically. Check the logs for warnings.

### Atlas Embeddings Memory Issues

For large dimension vectors, consider:
- Reducing dimensions
- Processing in batches
- Clearing vector cache

### Ego Guard Forge Policy Evaluation

If policies are not evaluating correctly:
- Check that rules match context keys exactly
- Review audit trail for evaluation history
- Ensure policies are enabled

### Prism Facet Transformations

If transformations are not working:
- Check transformation type is supported
- Verify data type matches transformation requirements
- Review facet metadata for configuration

## Related Documentation

- [UOR Integration Guide](./UOR_INTEGRATION_GUIDE.md)
- [UOR Foundation](https://uor.foundation/)
- [UOR Foundation GitHub](https://github.com/UOR-Foundation)
