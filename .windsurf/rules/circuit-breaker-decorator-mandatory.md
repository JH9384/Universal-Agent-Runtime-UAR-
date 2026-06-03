---
description: Circuit breakers must be registered via the decorator or get_circuit_breaker for observability
tags: [bug-pattern, circuit-breaker, external-services, observability]
globs: ["uar/skills/*.py", "uar/integrations/*.py"]
---

# Circuit Breaker Registry Rule

## Rule

Any skill or integration that calls an **external service** (HTTP API, CLI tool, network protocol, remote database) **MUST** use one of:

1. `@with_circuit_breaker(service_name, ...)` decorator on the skill function.
2. `get_circuit_breaker(service_name, ...)` to create/retrieve the CB, ensuring it enters the global registry.

**NEVER** instantiate `CircuitBreaker(...)` directly at module level in a skill or integration file.

## Why

Standalone `CircuitBreaker` instances are invisible to the operator dashboard and health endpoints:

- `GET /api/health/circuit-breakers` iterates `_circuit_breakers` registry — standalone CBs are absent.
- `POST /api/health/circuit-breakers/{name}/reset` looks up the registry — standalone CBs cannot be reset.
- Operators cannot see degraded external services in the topology graph.

## Detect

Forbidden pattern:

```python
from uar.core.circuit_breaker import CircuitBreaker

_my_cb = CircuitBreaker("my_service", ...)   # ← invisible to registry

def my_skill(ctx):
    result = _my_cb.call(lambda: external_call())
```

Correct pattern A — decorator:

```python
from uar.core.circuit_breaker_decorator import with_circuit_breaker

@with_circuit_breaker("my_service", failure_threshold=3, recovery_timeout=30.0)
def my_skill(ctx):
    return external_call()
```

Correct pattern B — registry helper:

```python
from uar.core.circuit_breaker_decorator import get_circuit_breaker

_my_cb = get_circuit_breaker("my_service", failure_threshold=3, recovery_timeout=30.0)

def my_skill(ctx):
    result = _my_cb.call(lambda: external_call())
```

## Additional Rule: No Circuit Breakers for Local Computation

**NEVER** wrap purely local CPU-bound work (SymPy, NumPy, crypto, image processing, unit conversions) with a circuit breaker. Circuit breakers are for **external service failure isolation**, not local error handling. Use plain `try/except` for local operations.

## Known Offenders (Fixed)

- `uar/skills/ollama_generate.py` — standalone `_ollama_cb`.
- `uar/skills/autonomi_storage.py` — standalone `_autonomi_cb`.
- `uar/skills/graphrag_skills.py` — standalone `_graphrag_cb`.
- `uar/skills/cipher_ops.py` — CB wrapping local crypto ops.
- `uar/skills/math_compute.py` — CB wrapping SymPy.
- `uar/skills/physics_compute.py` — CB wrapping astropy.
- `uar/skills/stem_extended.py` — dead `_cb` factory.
