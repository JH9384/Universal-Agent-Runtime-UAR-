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

## Future Expansion

| Feature | Description | Phase |
|---------|-------------|-------|
| Effectiveness Rankings | Outcome-based type leaderboard | Ω-6a |
| Decay model | Time-weighted feedback | Ω-6a |
| Drift detection | Recent vs historical rate change | Ω-6a |
| Confidence Calibration | Predicted vs actual accuracy | Ω-6b |
| Replay Integration | Outcome → replay deep links | Ω-6c |
| Operator-specific models | Per-user preference tracking | Ω-6d |
| Ensemble confidence | Blend multiple heuristics | Ω-6e |
| A/B testing | Controlled modifier experiments | Ω-6f |

## Safety Guarantees

1. **Modifier never exceeds 1.5** — prevents over-confidence
2. **Modifier never drops below 0.5** — prevents suppression
3. **No adaptation without 10+ impressions** — prevents noise
4. **Pure function from data** — no hidden state
5. **Best-effort wrapping** — adaptive failures don't break recommendations
