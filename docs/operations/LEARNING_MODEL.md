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

## Future Expansion

| Feature | Description | Phase |
|---------|-------------|-------|
| Decay model | Time-weighted feedback | Ω-5.5 |
| Category-level modifiers | Different thresholds per category | Ω-5.5 |
| Operator-specific models | Per-user preference tracking | Ω-5.6 |
| Ensemble confidence | Blend multiple heuristics | Ω-5.7 |
| A/B testing | Controlled modifier experiments | Ω-5.8 |

## Safety Guarantees

1. **Modifier never exceeds 1.5** — prevents over-confidence
2. **Modifier never drops below 0.5** — prevents suppression
3. **No adaptation without 10+ impressions** — prevents noise
4. **Pure function from data** — no hidden state
5. **Best-effort wrapping** — adaptive failures don't break recommendations
