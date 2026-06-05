---
description: Prevent silent parameter shadowing in global mutable registries
tags: [bug-pattern, concurrency, globals]
---

# Global Mutable Registry Anti-Pattern

## Rule

When a module exposes a `get_or_create()` helper backed by a **global mutable dict/registry**, it must never silently ignore configuration parameters when the named entry already exists.

## Why

Python decorators and module-level imports create objects at import time. If two decorators register the same service name with different configs (e.g. different `failure_threshold`), the second decorator's parameters are silently discarded. This causes:

- **Silent misconfiguration** — the actual runtime config differs from the source code.
- **Heisenbugs** — behavior changes depending on import order.
- **Maintenance traps** — changing one decorator's params appears to have no effect.

## Detect

Look for this pattern:

```python
_REGISTRY: dict[str, Any] = {}
_REGISTRY_LOCK = threading.Lock()

def get_thing(name: str, config_param: int = 3) -> Any:
    with _REGISTRY_LOCK:
        if name not in _REGISTRY:
            _REGISTRY[name] = Thing(name, config_param=config_param)
        return _REGISTRY[name]   # ← silently ignores config_param on reuse
```

## Fix

### Option A — Warn on mismatch (recommended for existing code)

```python
def get_thing(name: str, config_param: int = 3) -> Any:
    with _REGISTRY_LOCK:
        if name not in _REGISTRY:
            _REGISTRY[name] = Thing(name, config_param=config_param)
        else:
            existing = _REGISTRY[name]
            if existing.config_param != config_param:
                logger.warning(
                    "Thing %r already exists with config_param=%s; "
                    "requested config_param=%s ignored.",
                    name, existing.config_param, config_param,
                )
        return _REGISTRY[name]
```

### Option B — Key by full configuration

```python
def get_thing(name: str, config_param: int = 3) -> Any:
    key = (name, config_param)
    with _REGISTRY_LOCK:
        if key not in _REGISTRY:
            _REGISTRY[key] = Thing(name, config_param=config_param)
        return _REGISTRY[key]
```

### Option C — Raise on mismatch

```python
def get_thing(name: str, config_param: int = 3) -> Any:
    with _REGISTRY_LOCK:
        if name not in _REGISTRY:
            _REGISTRY[name] = Thing(name, config_param=config_param)
        elif _REGISTRY[name].config_param != config_param:
            raise RuntimeError(
                f"Thing {name!r} already registered with "
                f"config_param={_REGISTRY[name].config_param}, "
                f"cannot change to {config_param}."
            )
        return _REGISTRY[name]
```

## Test

Always add a regression test that calls the getter twice with different params and asserts on one of:

- A warning is logged.
- A distinct object is returned (Option B).
- An exception is raised (Option C).

## Known Offenders (Fixed)

- `uar/core/circuit_breaker_decorator.py::get_circuit_breaker()` — warns on param mismatch.
- `uar/core/skill_cache.py::get_skill_cache()` — warns on maxsize mismatch.

## Related Patterns

- `duplicate-routes-dead-code.md` — global mutable state in routing.
- `async-polling.md` — global mutable state in async loops.
