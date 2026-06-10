# D5Q Evidence Pack API Contract

## Status

D5Q defines the Evidence Pack v2 API contract before implementation.

## Purpose

Specify the read-only API behavior, response shape, query parameters, auth expectations, and missing-data semantics for Evidence Pack v2.

## Endpoint

```text
GET /api/uar/evidence-pack/{run_id}
```

## Auth Requirement

The endpoint must require the same authenticated API access pattern used by protected UAR operational endpoints.

Minimum permission expectation:

```text
operator/read
```

If the existing auth model does not expose `operator/read`, use the nearest read-capable authenticated role and document the mapping.

## Query Parameters

| Parameter | Type | Default | Meaning |
| --- | --- | ---: | --- |
| `include_markdown` | boolean | `false` | Include rendered Markdown summary in response |
| `include_unavailable` | boolean | `true` | Include unavailable sections with explicit missing reasons |
| `signal_id` | string | absent | Optional signal linkage |
| `recommendation_id` | string | absent | Optional recommendation linkage |
| `outcome_id` | string | absent | Optional operator outcome linkage |

## Response: Success

HTTP status:

```text
200 OK
```

Response shape:

```json
{
  "status": "ok",
  "run_id": "run-id",
  "evidence_pack": {
    "evidence_pack_id": "evidence-pack:run-id",
    "generated_at": "timestamp",
    "authority_tag": "tag-or-contract-version",
    "run_id": "run-id",
    "signal": {
      "available": false,
      "source": "signal",
      "data": null,
      "missing": ["signal data not provided"]
    },
    "mission_control": {
      "available": true,
      "source": "mission_control",
      "data": {},
      "missing": []
    },
    "replay": {
      "available": false,
      "source": "replay",
      "data": null,
      "missing": ["replay evidence not provided"]
    },
    "burnin": {
      "available": true,
      "source": "burnin",
      "data": {},
      "missing": []
    },
    "certification": {
      "available": true,
      "source": "certification",
      "data": {},
      "missing": []
    },
    "trust": {
      "available": false,
      "source": "trust",
      "data": null,
      "missing": ["trust evidence not provided"]
    },
    "outcome": {
      "available": false,
      "source": "outcome",
      "data": null,
      "missing": ["operator outcome not provided"]
    },
    "closure": {
      "available": false,
      "source": "closure",
      "data": null,
      "missing": ["closure state not provided"]
    }
  },
  "markdown": null
}
```

If `include_markdown=true`, `markdown` contains the rendered Evidence Pack v2 Markdown string.

## Missing Data Semantics

Missing data is not an API failure when the run can still produce a partial Evidence Pack.

The endpoint must return explicit unavailable sections:

```json
{
  "available": false,
  "source": "replay",
  "data": null,
  "missing": ["replay evidence not provided"]
}
```

## Error Responses

### Unauthorized

```text
401 Unauthorized
```

Used when auth is missing or invalid.

### Forbidden

```text
403 Forbidden
```

Used when auth exists but lacks read permission.

### Invalid Run ID

```text
422 Unprocessable Entity
```

Used when `run_id` is empty or invalid.

### Unexpected Builder Failure

```text
500 Internal Server Error
```

Used only for unexpected failures. Missing evidence should not produce 500.

## Read-Only Contract

The endpoint must not:

- create outcomes,
- update trust,
- mutate run records,
- trigger burn-in,
- trigger replay reconstruction side effects,
- change certification state,
- promote artifacts,
- write files under `reports/`,
- write files under `docs/certification/artifacts/`.

## Implementation Dependency

The endpoint must use:

```text
uar/core/evidence_pack.py
```

The API layer may gather source data, but pack assembly must remain backed by the D5E builder.

## Test Requirements Before Router Implementation

D5R should add tests for:

1. authenticated success response,
2. missing sections remain explicit,
3. markdown optional rendering,
4. invalid `run_id` handling,
5. unauthenticated rejection,
6. no mutation side effects,
7. response shape stability.

## Guardrails

- Do not implement router code in D5Q.
- Do not weaken D4G warning gates.
- Do not make evidence-pack generation write artifacts from the API.
- Preserve local/operator scripts as first-class workflow.
