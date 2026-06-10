# D5R Evidence Pack API Test Scaffold

## Status

D5R adds skipped tests for the Evidence Pack v2 API contract before router implementation.

## Purpose

Preserve the D5Q API contract in test form while avoiding regression failures before D5S implements the router.

## Test File

`tests/api/test_evidence_pack_api_contract.py`

## Current Behavior

The test module is skipped with reason:

```text
D5R contract scaffold only; enable during D5S router implementation
```

## Contract Coverage

The scaffold captures tests for:

1. authentication requirement,
2. response envelope shape,
3. section availability shape,
4. optional markdown rendering,
5. explicit missing-section behavior,
6. invalid run ID behavior,
7. read-only/no side-effect guarantees.

## Operational Meaning

D5R locks the expected API behavior before code is wired, preventing router implementation from drifting away from the D5Q contract.

## Guardrails

- Tests remain skipped until D5S router implementation.
- Do not weaken D4G warning gates.
- Do not implement router code in D5R.
- Do not add artifact-writing behavior to the API.
