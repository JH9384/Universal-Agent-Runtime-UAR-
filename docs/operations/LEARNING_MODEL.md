# UAR Learning Model (Omega-5)

## Overview

The UAR learning model is not machine learning. It is **operational learning** —
structured, explainable heuristics that accumulate evidence from system behavior
and operator judgment, then use that evidence to improve recommendations.

## Architecture

```
Pattern
  ↓
Recommendation
  ↓
Operator Judgment
  ↓
Quality Measurement
  ↓
Adaptive Confidence
```

| Phase | Capability | Status |
|-------|------------|--------|
| Ω-5.1 | Pattern recognition (recurrence, recovery, topology) | ✅ |
| Ω-5.2 | Feedback loop (accept / reject / dismiss) | ✅ |
| Ω-5.3 | Quality metrics (shown, accepted, rates) | ✅ |
| Ω-5.4 | Adaptive confidence | ✅ |
| Ω-5.5+ | Predictive ranking, decay, ensemble | Future |

## Confidence Formula

```
adaptive_confidence = base_confidence × operator_modifier
```

### base_confidence

Computed by individual recommendation engines using explainable heuristics:

| Source | Heuristic |
|--------|-----------|
| Recurrence engine | `0.5 + occurrences × 0.05` (capped at 0.95) |
| Recovery atlas | Historical success rate |
| Topology evolution | Fixed thresholds (0.7 – 0.8) |
| Governance trends | Trend severity (0.8 – 0.9) |

### operator_modifier

A slowly-moving scalar that rewards or penalizes based on operator feedback.

**Initial value:** `1.0`

**Evidence gate:** `shown_count >= 10` before any deviation from 1.0.

This prevents a single accept from inflating confidence unrealistically.

**Adjustment rules:**

| Signal | Condition | Delta |
|--------|-----------|-------|
| High acceptance | `acceptance_rate > 0.90` | `+0.10` |
| Good acceptance | `acceptance_rate > 0.80` | `+0.05` |
| High rejection | `rejection_rate > 0.60` | `-0.10` |
| High dismissal | `dismissal_rate > 0.70` | `-0.05` |

**Clamp:** `0.5 ≤ modifier ≤ 1.5`

This prevents runaway behavior in either direction.

## Minimum Evidence Threshold

No adaptation occurs until a recommendation has been shown at least **10 times**.

Rationale:
- `1 accept / 1 shown` is 100% acceptance but meaningless
- `8 accept / 10 shown` is strong signal
- Threshold ensures statistical relevance

## Time and Decay

Current model: **no decay**.

All feedback is weighted equally regardless of age. This is intentional for
Ω-5.4 simplicity. Future phases may introduce:

- Exponential decay on older feedback
- Time-windowed quality windows (7-day, 30-day)
- Seasonal correction

## Anti-Feedback-Trap Design

The modifier is **recomputed from raw store data on every request**, not
persisted or cached. This prevents:

```
confidence ↑ → shown more → accepted more → confidence ↑↑
```

Because the modifier reflects actual operator behavior, not a self-referential
loop.

## Outcome Attribution (Ω-5.5)

Acceptance rate measures **popularity**.
Outcome tracking measures **effectiveness**.

When an operator accepts a recommendation, the system records the acceptance.
Later, an outcome can be recorded:

| Outcome | Meaning |
|---------|---------|
| resolved | The failure or issue the recommendation addressed was fixed |
| recurred | The failure or issue came back |
| unknown | No follow-up information available |

### Resolution Rate

```
resolution_rate = resolved / (resolved + recurred)
```

This answers: "Of the recommendations that were accepted and had a known
outcome, what fraction actually helped?"

### API

- `POST /api/uar/recommendations/outcome`
  - Body: `{ "recommendation_id": "...", "outcome_type": "resolved|recurred|unknown" }`

- `GET /api/uar/recommendations/quality` now includes:
  - `resolved_count` and `recurred_count` per recommendation
  - `resolution_rate` per recommendation
  - `total_resolved`, `total_recurred`, `overall_resolution_rate`

### Why Outcomes Matter

A recommendation with 95% acceptance could mean:
- It was genuinely useful, or
- It sounded reasonable but did not help

Outcome attribution distinguishes these cases.

## Explainability

Every recommendation response includes:

```json
{
  "confidence": 0.72,
  "base_confidence": 0.65,
  "adaptive_modifier": 1.11
}
```

Operators can see exactly why a recommendation received its score.

## Outcome Intelligence (Ω-6a)

Ω-6a extracts operational value from the outcome corpus created in Ω-5.5.

### Effectiveness Rankings

```
GET /api/uar/recommendations/effectiveness
```

Returns a leaderboard of recommendation types ranked by how often they actually resolve issues.

```json
{
  "recommendation_types": [
    {
      "type": "restart_service",
      "sample_size": 87,
      "resolution_rate": 0.94,
      "smoothed_resolution_rate": 0.93,
      "weighted_resolution_rate": 0.91,
      "drift": -0.03
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `resolution_rate` | Raw resolved / (resolved + recurred) |
| `smoothed_resolution_rate` | Bayesian-smoothed with Laplace prior |
| `weighted_resolution_rate` | Time-decay weighted (older outcomes count less) |
| `drift` | Recent rate minus historical rate (early warning) |

### Bayesian Smoothing

Prevents ranking noise for small samples:

```
smoothed_rate = (resolved + alpha) / (total + alpha + beta)
```

Default: alpha = 1, beta = 1. This means a type with 1/1 outcomes
gets smoothed to ~0.33, not 1.0.

### Time Decay

Older outcomes count less via exponential decay:

```
weight = e^(-ln(2) * age_days / half_life)
```

Default half-life: 30 days.

| Age | Weight |
|-----|--------|
| Today | 1.00 |
| 30 days | 0.50 |
| 90 days | 0.13 |

This allows historical memory and recent adaptation simultaneously.

### Drift Detection

Compares the last 30 days against all prior history:

```
drift = recent_resolution_rate - historical_resolution_rate
```

A drift of -0.31 means:

> What used to work is no longer working.

This is often more valuable than the raw ranking.

### Minimum Sample Threshold

Types with fewer than 5 outcomes are excluded from rankings.
This prevents volatile noise from dominating the leaderboard.

## Confidence Calibration (Ω-6b)

Ω-6b measures whether predicted confidence matches actual outcomes.

### Calibration Endpoint

```
GET /api/uar/recommendations/calibration
```

Returns:

```json
{
  "overall_calibration_error": 0.15,
  "mean_predicted_confidence": 0.82,
  "mean_actual_resolution_rate": 0.67,
  "sample_size": 124,
  "reliability_buckets": [
    {
      "bucket": "0.80-0.90",
      "predicted_avg": 0.85,
      "actual_rate": 0.84,
      "sample_size": 45,
      "calibration_error": 0.01
    },
    {
      "bucket": "0.90-1.00",
      "predicted_avg": 0.95,
      "actual_rate": 0.62,
      "sample_size": 23,
      "calibration_error": 0.33
    }
  ]
}
```

### Interpreting Calibration Error

| Error | Meaning |
|-------|---------|
| +0.40 | **Overconfident** — predicted 0.95, actual 0.55 |
| -0.27 | **Underconfident** — predicted 0.55, actual 0.82 |
| +0.02 | **Well calibrated** — predicted 0.78, actual 0.80 |

### Reliability Buckets

Confidence predictions are grouped into 0.1-wide buckets:

```
0.0-0.1  0.1-0.2  0.2-0.3  ...  0.9-1.0
```

Each bucket reports:
- `predicted_avg`: average confidence predicted for that bucket
- `actual_rate`: actual resolution rate for recommendations in that bucket
- `calibration_error`: predicted_avg minus actual_rate

Buckets with fewer than 1 sample are excluded.

### Why Calibration Matters

Well-calibrated confidence means operators can trust the score.

If confidence says 0.90 but actual resolution is 0.55,
operators learn to ignore the score. The system loses credibility.

Calibration turns confidence from a decoration into a reliable signal.

## Replay Intelligence (Ω-6c)

Ω-6c links recommendations to outcomes and the runs that produced them,
forming an operational knowledge graph.

### Evidence Endpoint

```
GET /api/uar/recommendations/evidence
```

Aggregate (no query param):

```json
{
  "recommendation_types": [
    {
      "type": "restart_service",
      "resolution_rate": 0.91,
      "sample_size": 87,
      "supporting_replays": 42
    }
  ]
}
```

Specific (`?recommendation_id=abc123`):

```json
{
  "recommendation_id": "abc123",
  "category": "remediate",
  "source": "pattern",
  "title": "Restart service",
  "confidence": 0.85,
  "run_id": "run-456",
  "outcome": "resolved",
  "outcome_recorded_at": 1717234567
}
```

### Evidence Linkage Model

```
Recommendation
     ↓ (metadata)
Confidence
     ↓ (outcome)
Resolved/Recurred
     ↓ (run_id)
Replay
```

This creates a navigable path:

```
Operator: Why is this recommendation trusted?
System:  Here are 42 historical runs with outcomes.
Operator: Show me one that worked.
System:  Replay run-456 — resolved.
```

### Supporting Replays

`supporting_replays` counts unique `run_id` values linked to resolved or recurred outcomes for each recommendation type. This answers:

> How much evidence backs this recommendation?

A high resolution rate with only 2 supporting replays is suspicious.
A moderate resolution rate with 87 supporting replays is trustworthy.

### Run ID Capture

When a recommendation is generated, the first `affected_run` is stored alongside its metadata. This links the recommendation to a representative historical run without requiring schema changes to the outcomes table.

## Future Expansion

| Feature | Description | Phase |
|---------|-------------|-------|
| Effectiveness Rankings | Outcome-based type leaderboard | Ω-6a |
| Decay model | Time-weighted feedback | Ω-6a |
| Drift detection | Recent vs historical rate change | Ω-6a |
| Confidence Calibration | Predicted vs actual accuracy | Ω-6b |
| Replay Intelligence | Evidence linkage and aggregation | Ω-6c |
| Operator-specific models | Per-user preference tracking | Ω-6d |
| Ensemble confidence | Blend multiple heuristics | Ω-6e |
| A/B testing | Controlled modifier experiments | Ω-6f |

## Safety Guarantees

1. **Modifier never exceeds 1.5** — prevents over-confidence
2. **Modifier never drops below 0.5** — prevents suppression
3. **No adaptation without 10+ impressions** — prevents noise
4. **Pure function from data** — no hidden state
5. **Best-effort wrapping** — adaptive failures don't break recommendations
