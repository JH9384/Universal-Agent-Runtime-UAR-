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

| Feature | Description | Phase | Status |
| --- | --- | --- | --- |
| Effectiveness Rankings | Outcome-based type leaderboard | Ω-6a | ✅ |
| Decay model | Time-weighted feedback | Ω-6a | ✅ |
| Drift detection | Recent vs historical rate change | Ω-6a | ✅ |
| Confidence Calibration | Predicted vs actual accuracy | Ω-6b | ✅ |
| Replay Intelligence | Evidence linkage and aggregation | Ω-6c | ✅ |
| Trust Computation | Composable operational belief metric | Ω-7a | ✅ |
| Trust Ranking | Optional trust-weighted ordering | Ω-7b | ✅ |
| Trust Visibility | Operator-facing trust labels | Ω-7c | Future |
| Adaptive Confidence Correction | Runtime confidence adjustment | Ω-7d | Future |
| Type-Level Calibration | Per-type calibration | Ω-8 | Future |
| Autonomous Trust Tuning | Self-adjusting weights | Ω-9 | Future |
| Operator-specific models | Per-user preference tracking | Ω-6d | Future |
| Ensemble confidence | Blend multiple heuristics | Ω-6e | Future |
| A/B testing | Controlled modifier experiments | Ω-6f | Future |

## Adaptive Trust Engine (Ω-7a)

Ω-7a composes effectiveness, calibration, evidence, and drift into a
single trust score per recommendation type.

### Trust Endpoint

```
GET /api/uar/recommendations/trust
```

Returns:

```json
{
  "generated_at": 1717234567,
  "system_calibration_error": 0.05,
  "recommendation_types": [
    {
      "type": "restart_service",
      "trust_score": 0.82,
      "effectiveness_component": 0.91,
      "calibration_component": 0.95,
      "evidence_component": 0.70,
      "drift_penalty": 0.05
    }
  ]
}
```

### Trust Formula

```
trust = (effectiveness + calibration + evidence) / 3 - drift_penalty
```

All values clamped to [0, 1].

| Component | Source | Meaning |
|-----------|--------|---------|
| `effectiveness_component` | weighted_resolution_rate | How often this type resolves issues |
| `calibration_component` | 1 - abs(system_calibration_error) | Whether confidence predictions are trustworthy |
| `evidence_component` | sample_size + replays | How much data backs this type |
| `drift_penalty` | max(0, -drift) | Penalty when recent effectiveness drops below historical |

### Why Trust Matters

A recommendation can have high confidence but low trust.

Example:
- Confidence: 0.95 (predicted)
- Effectiveness: 0.40 (actual)
- Calibration error: +0.55 (overconfident)
- Drift: -0.30 (getting worse)

Trust score: ~0.15

The operator should know this before acting.

### Trust Thresholds

| Score | Interpretation |
|-------|----------------|
| 0.80+ | Highly trusted — reliable signal |
| 0.60-0.80 | Trusted — good signal, monitor |
| 0.40-0.60 | Watch — mixed evidence |
| 0.20-0.40 | Weak — insufficient evidence or poor calibration |
| <0.20 | Untrusted — do not rely on |

## Trust-Aware Recommendation Ranking (Ω-7b)

Ω-7b introduces optional trust-weighted ordering. Trust scores computed in
Ω-7a are now exposed on every recommendation response and can optionally
influence recommendation ordering.

### Soft Blend Formula

When enabled, the final rank score is computed as:

```text
final_rank = 0.7 × confidence + 0.3 × trust_score
```

This is a **weighted sum**, not multiplication. Multiplication would be brutal:

- `confidence = 0.90, trust = 0.50 → product = 0.45` (collapse)
- `confidence = 0.90, trust = 0.50 → blend = 0.78` (gentler)

The weighted blend allows a highly confident recommendation to maintain a
reasonable score even when trust is moderate.

### Priority Band Preservation

**Critical** recommendations do not suddenly lose to **low** recommendations
because the low-priority item accumulated historical trust.

Severity remains the primary ordering signal. Trust only influences ordering
within the same priority band.

### Feature Flag

Disabled by default:

```text
ENABLE_TRUST_RANKING=false
```

This creates two operational modes:

| Mode | Flag | Behavior |
| --- | --- | --- |
| Observation | `false` | Trust scores exposed; no behavior change |
| Intervention | `true` | Recommendations re-ranked by blended score |

### API Changes

`GET /api/uar/recommendations` now always includes:

```json
{
  "trust_ranking_enabled": false,
  "recommendations": [
    {
      "trust_score": 0.42,
      ...
    }
  ],
  "trust": {
    "generated_at": 1717257600,
    "system_calibration_error": -0.05,
    "recommendation_types": [
      {"type": "remediate", "trust_score": 0.42}
    ]
  }
}
```

When `ENABLE_TRUST_RANKING=true`:

- `trust_ranking_enabled` becomes `true`
- Recommendations are re-sorted using the blended score within priority bands

### Burn-In Guidance

During initial deployment, run with `ENABLE_TRUST_RANKING=false` and monitor:

1. **Trust vs Resolution correlation** — High trust should correlate with high
   resolution rates.
2. **Trust vs Acceptance correlation** — High trust should eventually correlate
   with high operator acceptance.
3. **Confidence vs Trust divergence** — Find cases where `confidence > 0.9` and
   `trust < 0.4`, or vice versa. These prediction disagreements often uncover
   hidden issues.

Only enable ranking after validating that trust scores behave as expected.

## Learning Architecture Freeze v1

**Date:** 2026-06-01
**Status:** ACTIVE

The UAR learning subsystem is now internally coherent through Ω-7b. No new
learning logic will be added until operational validation completes.

### What is Frozen

| Layer | Status |
| --- | --- |
| Ω-5.1 Pattern Recognition | ✅ Locked |
| Ω-5.2 Feedback Collection | ✅ Locked |
| Ω-5.3 Quality Metrics | ✅ Locked |
| Ω-5.4 Adaptive Confidence | ✅ Locked |
| Ω-5.5 Outcome Attribution | ✅ Locked |
| Ω-6a Effectiveness Intelligence | ✅ Locked |
| Ω-6b Calibration Intelligence | ✅ Locked |
| Ω-6c Replay Intelligence | ✅ Locked |
| Ω-7a Trust Computation | ✅ Locked |
| Ω-7b Trust-Aware Ranking | ✅ Locked |

### What is NOT Frozen

- Bug fixes
- Instrumentation additions
- Documentation updates
- Dashboard visualizations
- Operational validation tooling

### When to Unfreeze

After Ω-7B.1 Operational Validation exit criteria are met.

## Ω-7B.1 Operational Validation

Ω-7B.1 is a structured burn-in phase to gather evidence before trust becomes a
primary decision signal. It is not feature development. It is operational
observation.

### Objectives

Collect four metrics that validate whether trust scores are behaving as
intended.

#### Metric 1: Trust Distribution

How many recommendation types fall into each trust band?

| Band | Range | Meaning |
| --- | --- | --- |
| Highly Trusted | 0.80+ | Reliable signal |
| Trusted | 0.60–0.80 | Good signal, monitor |
| Watch | 0.40–0.60 | Mixed evidence |
| Weak | 0.20–0.40 | Insufficient evidence or poor calibration |
| Untrusted | <0.20 | Do not rely on |

**Healthy:** A natural spread. Not everything clusters at 0.65–0.80.

**Unhealthy:** All scores compressed into a narrow band. The trust model is not
discriminating.

#### Metric 2: Ranking Delta

For each recommendation, compare:

```text
confidence_rank   (where it would be with Ω-5.x alone)
trust_rank        (where it is with Ω-7b)
```

| Pattern | Meaning |
| --- | --- |
| confidence_rank = 1, trust_rank = 4 | High confidence, historically weak |
| confidence_rank = 5, trust_rank = 1 | Low confidence, historically strong |

These deltas are the most interesting cases. They indicate prediction
disagreement between current signal and historical evidence.

#### Metric 3: Outcome Correlation

Does higher trust correlate with higher actual resolution?

```text
Spearman(trust_score, resolution_rate) > 0.5   → good
Spearman(trust_score, resolution_rate) < 0.0   → trust formula needs adjustment
```

Track this weekly. Do not expect instant correlation — evidence accumulates.

#### Metric 4: Drift Discovery

Watch for:

```text
high confidence + high trust + negative drift
```

These are emerging failures. The recommendation type historically worked, is
still trusted, but recent outcomes are degrading. This is exactly what drift
penalty is meant to surface.

### Duration

2–4 weeks or sufficient recommendation volume.

Minimum recommendation volume:

- 50+ distinct recommendations shown
- 20+ with outcomes (resolved / recurred)
- 10+ per recommendation type

### Exit Criteria

Burn-in completes when ALL of the following are true:

1. **Trust Stability**
   - Trust scores for established types vary by < 0.10 week-over-week
   - New types are the only source of movement

2. **Calibration Stability**
   - Reliability bucket errors vary by < 0.05 week-over-week
   - No bucket swings > 0.15 without clear cause

3. **Ranking Stability**
   - Top-5 trust types remain consistent
   - < 20% of types change trust band weekly

4. **Resolution Correlation**
   - Positive Spearman correlation between trust_score and resolution_rate
   - Correlation coefficient >= 0.3 (minimum)
   - Correlation coefficient >= 0.5 (preferred)

### Tooling

Use the `/api/uar/recommendations` endpoint with `ENABLE_TRUST_RANKING=false`
(observation mode). Trust scores are exposed but do not influence ordering.

Use the `/api/uar/recommendations/trust` endpoint for aggregate trust views.

Use the `/api/uar/recommendations/quality` endpoint for outcome tracking.

Use the `/api/uar/recommendations/effectiveness` endpoint for effectiveness
leaderboards.

### Post-Burn-In Decision Matrix

| Condition | Action |
| --- | --- |
| All exit criteria met | Proceed to Ω-7c Trust Visibility |
| Trust distribution compressed | Investigate formula weights |
| No resolution correlation | Extend burn-in or adjust evidence_component |
| High drift without detection | Tighten drift_penalty threshold |
| Ranking thrashes | Increase evidence gate before trust applies |

## Safety Guarantees

1. **Modifier never exceeds 1.5** — prevents over-confidence
2. **Modifier never drops below 0.5** — prevents suppression
3. **No adaptation without 10+ impressions** — prevents noise
4. **Pure function from data** — no hidden state
5. **Best-effort wrapping** — adaptive failures don't break recommendations
