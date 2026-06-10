# D5Y Evidence Pack Authority Map

## Status

D5Y records the authoritative Evidence Pack v2 implementation, validation, API, smoke, and CI gates after D5X.

## Current Evidence Pack Position

Evidence Pack v2 is now implemented across:

- core read-only builder,
- local renderer,
- JSON-input CLI builder,
- live evidence capture script,
- Make target smoke workflow,
- promoted artifact hygiene,
- API readiness decision,
- API contract,
- read-only API router,
- API auth alignment,
- active API contract tests,
- live API smoke,
- repeatable API smoke Make target,
- CI-visible Evidence Pack gates.

## Authoritative Tags

| Lane | Tag | Meaning |
| --- | --- | --- |
| D5E | `v1.2.19-d5e-evidence-pack-builder` | Read-only core Evidence Pack builder |
| D5F | `v1.2.20-d5f-evidence-pack-renderer` | Sample renderer script |
| D5G | `v1.2.21-d5g-evidence-pack-cli` | JSON-input builder command |
| D5H | `v1.2.23-d5h-live-evidence-validated` | Live capture validated |
| D5I | `v1.2.24-d5i-evidence-capture-make-target` | Make target added |
| D5J | `v1.2.25-d5j-evidence-artifact-hygiene` | Artifact hygiene |
| D5K | `v1.2.26-d5k-make-evidence-capture` | Make capture validation |
| D5L | `v1.2.27-d5l-evidence-promotion-template` | Promotion template |
| D5M | `v1.2.32-d5m-final-artifact-authority` | Final promoted artifact authority |
| D5N | `v1.2.33-d5n-evidence-promotion-index` | Promotion index |
| D5O | `v1.2.34-d5o-evidence-pack-operator-readme` | Operator README |
| D5P | `v1.2.35-d5p-evidence-pack-api-readiness` | API readiness decision |
| D5Q | `v1.2.36-d5q-evidence-pack-api-contract` | API contract |
| D5R | `v1.2.37-d5r-evidence-pack-api-test-scaffold` | API test scaffold |
| D5S | `v1.2.38-d5s-evidence-pack-router` | Read-only API router |
| D5T | `v1.2.39-d5t-evidence-pack-api-auth` | API auth alignment |
| D5U | `v1.2.40-d5u-evidence-pack-api-contract-active` | Active API contract tests |
| D5V | `v1.2.42-d5v-live-smoke-runtime-aligned` | Live API smoke runtime-aligned evidence |
| D5W | `v1.2.43-d5w-evidence-pack-api-smoke-target` | Repeatable API smoke Make target |
| D5X | `v1.2.44-d5x-evidence-pack-ci-gates` | CI-visible Evidence Pack gates |

## Current Authoritative Commands

```bash
python scripts/evidence_pack/render_sample_evidence_pack.py --run-id <run-id>
python scripts/evidence_pack/build_evidence_pack.py --run-id <run-id>
./scripts/evidence_pack/capture_live_evidence_pack.sh
make d5h-evidence-capture
make d5w-evidence-pack-api-smoke
```

## Current Authoritative API

```text
GET /api/uar/evidence-pack/{run_id}
```

Supported query behavior:

- `include_markdown=true|false`
- `include_unavailable=true|false`
- `signal_id=<id>`
- `recommendation_id=<id>`
- `outcome_id=<id>`

## Current Authoritative CI Workflow

```text
.github/workflows/d5x-evidence-pack.yml
```

## Current Guardrails

- Evidence Pack generation is read-only.
- API endpoint is authenticated.
- Missing evidence is explicit and section-local.
- API does not write reports.
- API does not promote artifacts.
- API does not mutate outcomes, trust, runs, replay, burn-in, or certification.
- Live smoke remains operator-triggered through Make.
- CI gates do not require a live API server.

## Superseded / Clarified D5 Tags

| Tag | Reason |
| --- | --- |
| `v1.2.22-d5h-live-evidence-capture` | Script existed before validated live capture |
| `v1.2.28-d5m-evidence-promotion-smoke` | Created before artifacts were committed |
| `v1.2.29-d5m-evidence-promotion-validated` | Promotion doc committed, later artifact authority clarified |
| `v1.2.30-d5m-promotion-authority` | Authority note before force-added artifacts were committed |
| `v1.2.31-d5m-promoted-artifacts-committed` | Artifacts committed, superseded by final authority note |
| `v1.2.41-d5v-evidence-pack-live-api-smoke` | Live smoke doc initially expected old auth error text |

## Operational Meaning

Evidence Pack v2 is now productized enough for operator use and release validation. Further work should focus on data-source enrichment and UI integration rather than creating new evidence-pack frameworks.

## Guardrails

- Do not create a second Evidence Pack format.
- Do not weaken authentication or warning gates.
- Do not make API calls mutate runtime state.
- Do not promote generated artifacts without the D5L/D5N promotion path.
