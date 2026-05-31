# Replay Confidence Model v1

Status: Specification  
Trust Spine Phase: T1  
Primary Issue: #74  
Related Issue: #58

## Purpose

Replay Confidence is the first measurable trust primitive in UAR.

It answers:

> Can this run be replayed, reconstructed, and trusted?

## Inputs

Replay Confidence evaluates five evidence dimensions:

1. Event Completeness
2. Timeline Completeness
3. Artifact Completeness
4. Store Consistency
5. Replay Reconstruction Success

## Score Model

Each dimension produces a score from 0 to 100.

Recommended v1 weighting:

| Dimension | Weight |
| --- | ---: |
| Event Completeness | 30% |
| Timeline Completeness | 20% |
| Store Consistency | 20% |
| Replay Reconstruction Success | 20% |
| Artifact Completeness | 10% |

Formula:

```text
confidence_score =
  event_completeness * 0.30 +
  timeline_completeness * 0.20 +
  store_consistency * 0.20 +
  replay_reconstruction_success * 0.20 +
  artifact_completeness * 0.10
```

## Confidence Tiers

| Score | Tier | Meaning |
| ---: | --- | --- |
| 95-100 | Verified | Strong replay evidence |
| 85-94 | High | Replay is trustworthy with minor warnings |
| 70-84 | Medium | Replay is usable but needs review |
| 50-69 | Low | Replay is partial or degraded |
| 0-49 | Failed | Replay cannot be trusted |

## Warning Classes

Recommended warning codes:

- `missing_events`
- `invalid_event_schema`
- `timeline_gap`
- `store_record_missing`
- `store_event_mismatch`
- `reconstruction_failed`
- `artifact_missing`
- `legacy_event_shape`
- `partial_replay`

## API Shape

Recommended response shape:

```json
{
  "run_id": "run_123",
  "confidence": {
    "score": 96,
    "tier": "Verified",
    "warnings": [],
    "errors": [],
    "dimensions": {
      "event_completeness": 100,
      "timeline_completeness": 95,
      "store_consistency": 100,
      "replay_reconstruction_success": 100,
      "artifact_completeness": 90
    }
  }
}
```

## Implementation Target

Recommended module:

```text
uar/core/replay_confidence.py
```

Recommended entry point:

```python
score_replay(record: RunRecord) -> ReplayConfidenceReport
```

Recommended dependencies:

- `uar/core/replay.py`
- `uar/core/timeline.py`
- run store abstraction
- existing replay API endpoints

## Integration Points

Consumes:

- persisted run records
- runtime events
- replay summary
- timeline projection

Feeds:

- Burn-In Framework (#62)
- Certification Scoring (#70)
- Certification Engine (#57)
- Mission Control (#55/#72)
- Replay Explorer (#56)

## v1 Success Criteria

Replay Confidence v1 is complete when:

- score calculation exists
- warning generation exists
- API output exists
- tests cover complete, partial, legacy, and failed replay cases
- Mission Control can display confidence score/tier
- Certification Scoring can consume the report
