# D5E Read-Only Evidence Pack Builder

## Status

D5E defines the read-only Evidence Pack v2 builder design.

## Purpose

Create an implementation plan for generating Evidence Pack v2 artifacts without mutating runtime state.

## Inputs

Required:

- `run_id`

Optional:

- `signal_id`
- `recommendation_id`
- `outcome_id`
- `include_markdown`
- `include_json`

## Output

The builder returns an Evidence Pack v2 object with explicit availability markers.

## Availability Contract

Each section should include:

```json
{
  "available": true,
  "source": "source-name",
  "data": {},
  "missing": []
}
```

If unavailable:

```json
{
  "available": false,
  "source": "source-name",
  "data": null,
  "missing": ["reason"]
}
```

## Builder Responsibilities

1. Resolve run identity.
2. Fetch Mission Control snapshot.
3. Fetch replay confidence/explorer data when available.
4. Fetch latest burn-in report.
5. Fetch certification report.
6. Fetch trust/recommendation evidence when available.
7. Attach outcome data when available.
8. Produce JSON and markdown renderable output.

## Non-Responsibilities

The builder must not:

- create outcomes,
- update trust,
- mutate run records,
- trigger burn-in,
- trigger replay side effects,
- change certification state.

## Proposed Module

```text
uar/core/evidence_pack.py
```

## Proposed API Layer

Only after core builder tests pass:

```text
uar/api/routers/evidence_pack.py
GET /api/uar/evidence-pack/{run_id}
```

## Proposed Tests

- builder returns pack for valid run
- builder marks replay unavailable for missing run
- builder marks burn-in unavailable when no burn-in exists
- builder includes certification when available
- builder is read-only
- markdown render includes canonical D5B path

## Guardrails

- Reuse existing source data.
- Do not duplicate Mission Control logic.
- Do not duplicate replay explorer logic.
- Missing data must be explicit.
- Preserve run identity.
