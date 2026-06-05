---
description: Store iteration must defensively handle missing objects to prevent 500 errors
tags: [storage, error-handling, api, defensive]
---

# Store Iteration KeyError Defense Rule

## Problem
When iterating over store registries (runtimes, objects, etc.), the digest returned by the registry may reference an object that no longer exists or was never persisted. Calling `store.get_object(digest)` directly in a list comprehension or dict literal raises `KeyError`, producing an unhandled 500 response.

## Forbidden Pattern
```python
@router.get("/runtimes")
def get_runtimes(store: ObjectStore = Depends(get_store)):
    return {
        "runtimes": [
            {
                "attributes": store.get_object(digest).get("attributes", {}),
                # ^^^^^^^ KeyError if digest missing
            }
            for name, digest in store.list_runtimes().items()
        ]
    }
```

## Required Pattern
```python
@router.get("/runtimes")
def get_runtimes(store: ObjectStore = Depends(get_store)):
    runtimes = []
    for name, digest in sorted(store.list_runtimes().items()):
        try:
            obj = store.get_object(digest)
        except KeyError:
            obj = {}
        runtimes.append({
            "name": name,
            "digest": digest,
            "attributes": obj.get("attributes", {}),
        })
    return {"runtimes": runtimes}
```

## Enforcement
- Any endpoint that iterates over store.list_* results and fetches individual objects must guard `store.get_object(digest)` with a `try/except KeyError`.
- When an object is missing, return a safe default (empty dict, empty attributes) rather than crashing.

## Rationale
Registries and object stores can become inconsistent (orphaned digests, race conditions during deletion). Defensive iteration prevents transient store inconsistencies from becoming user-facing 500 errors.
