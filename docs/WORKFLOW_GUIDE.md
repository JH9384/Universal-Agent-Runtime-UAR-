# Workflow Guide

## Mental Model

```
objects → runtime → output → next runtime → output
```

## Example Workflow

```json
POST /workflows/run
{
  "inputs": ["sha256:a", "sha256:b"],
  "steps": [
    {"runtimeName": "sum_contents"},
    {"runtimeName": "identity_value"}
  ]
}
```

## Important Detail

Use `values` inside runtimes:

```python
sum(values)
```

This ensures chaining works correctly.

## Common Pitfall

Using raw `contents` can break chaining if previous output is wrapped.

## Debugging

1. Check step outputs
2. Inspect lineage
3. Re-run with same inputs
