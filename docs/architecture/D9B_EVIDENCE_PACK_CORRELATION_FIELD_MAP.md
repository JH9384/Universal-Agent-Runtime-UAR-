# D9B Evidence Pack Correlation Field Map

## Status

D9B maps recurrence-correlation enrichment fields to existing UAR sources.

## Baseline

- D8 recurrence-correlation baseline: `v1.5.0`
- D9 opening tag: `v1.5.1-d9a-evidence-pack-correlation-enrichment-opening`

## Purpose

Define exactly how Evidence Pack correlation enrichment derives data without inventing new authority, mutating trust, or creating a parallel report pipeline.

## Correlation section authority

The Evidence Pack correlation section is a read-only projection. It may summarize existing operator-loop state, but it must not create outcomes, modify trust, change incident recurrence, or persist derived conclusions as authoritative truth.

## Field map

| Evidence Pack field | Source | Required | Notes |
| --- | --- | --- | --- |
| `recommendation_id` | Mission Control linkage / Replay recommendation IDs | Yes when recommendation-linked | Must preserve the linked recommendation identity. |
| `run_id` | Replay Explorer selected run / Evidence Pack run ID | Yes | Must match the run being inspected. |
| `evidence_refs` | Mission Control linkage / run evidence refs | No | Usually `run:<run_id>`. Missing refs remain explicit. |
| `outcome_type` | Existing recommendation outcome endpoint/store | No | Values remain existing outcome vocabulary: `resolved`, `recurred`, `unknown`. |
| `trust_before` | Trust movement read model | No | Optional until historical movement records mature. |
| `trust_after` | Trust movement read model | No | Optional until historical movement records mature. |
| `trust_delta` | Trust movement read model | No | Optional; must not be recomputed by Evidence Pack if absent. |
| `later_recurrence_count` | Existing recurrence correlation preview | Yes for correlation records | Zero is meaningful. Missing data should render unavailable, not zero. |
| `later_recurrence_run_ids` | Existing recurrence correlation preview / incident recurrence summary | No | Preserve run IDs exactly. |
| `correlation_status` | Existing recurrence correlation preview | Yes for correlation records | Initial allowed values: `improved`, `recurred`, `no_later_recurrence`, `unknown`. |
| `generated_at` | Evidence Pack generation time | Yes | Existing Evidence Pack timestamp authority. |
| `authority_tag` | Evidence Pack builder/release tag | Yes | Should reference the D9 enrichment tag once implemented. |

## Rendering rules

- If no recommendation linkage exists, render the correlation section as unavailable.
- If recommendation linkage exists but no correlation data exists, render an explicit empty/read-only state.
- If recurrence count is zero, render it as `0`; do not treat it as missing.
- If trust movement fields are missing, render `unknown`; do not infer values.
- If outcome is missing, render `unknown`; do not create one.

## Guardrails

- No new trust formula.
- No automatic ranking change.
- No new outcome path.
- No duplicate incident store.
- No second trust score.
- No Evidence Pack mutation side effects.
- No duplicate evidence pipeline.

## Implementation target

D9C may add a reusable read-only Evidence Pack correlation section builder using this field map.
