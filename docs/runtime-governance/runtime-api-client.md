# Runtime API Client Guide

## Objective

Provide a lightweight operational interaction layer for runtime health inspection, telemetry retrieval, and operator-facing runtime workflows.

## Supported Operations

- runtime health retrieval
- telemetry retrieval
- runtime operational inspection

## Example

```python
from uar.core.runtime_api_client import RuntimeApiClient

client = RuntimeApiClient()

health = client.health()
telemetry = client.telemetry()
```

## Strategic Direction

The runtime API client evolves UAR from raw endpoint infrastructure into operator-oriented runtime interaction infrastructure.
