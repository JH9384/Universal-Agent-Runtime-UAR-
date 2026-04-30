# UAR Use Cases (Realistic)

## What UAR is good for now

### 1. Deterministic computation tracking
- Input objects → execution → output objects
- Full lineage trace

### 2. Safe runtime experimentation
- Register small runtime snippets
- Execute with bounds (timeout/memory)

### 3. Workflow prototyping
- Chain steps
- Validate transformations

### 4. Verifiable pipelines
- Re-run same inputs → same outputs

## What UAR is NOT yet

- Not a full agent system
- Not distributed
- Not production secure

## Example

```json
POST /agents/execution/run
{
  "runtimeName": "sum_contents",
  "inputs": ["sha256:...", "sha256:..."]
}
```

## Philosophy

UAR is about:

> Objects + Execution + Constraints + Lineage

Not chat, not autonomy, not hype.
