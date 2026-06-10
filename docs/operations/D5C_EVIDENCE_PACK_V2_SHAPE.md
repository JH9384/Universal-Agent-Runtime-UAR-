# D5C Evidence Pack v2 Shape

## Status

D5C defines the Evidence Pack v2 shape from the D5B operator evidence path.

## Purpose

Make UAR operational evidence exportable, reviewable, and tied to replay-backed operator action.

## Source Flow

```text
Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement
```

## Evidence Pack v2 Required Sections

### 1. Pack Metadata

Fields:

- evidence_pack_id
- generated_at
- generated_by
- environment
- authority_tag
- source_workflow

### 2. Signal Summary

Fields:

- signal_id
- signal_type
- severity
- source
- first_seen
- latest_seen
- affected_run_id
- affected_entity_id
- recommendation_id

### 3. Mission Control Snapshot

Fields:

- timestamp
- runtime_health
- replay_confidence
- certification
- burnin_status
- trust_summary
- entity_integrity
- entity_retention
- fleet_summary
- recent_warnings

### 4. Replay Evidence

Fields:

- run_id
- replay_available
- replay_confidence_score
- replay_tier
- warnings
- failure_path
- timeline_summary
- reconstruction_status

### 5. Burn-In Evidence

Fields:

- latest_burnin_status
- latest_burnin_score
- latest_burnin_level
- burnin_passed
- burnin_timestamp

### 6. Certification Evidence

Fields:

- certification_level
- certification_score
- violations
- evidence_weights
- timestamp

### 7. Trust Evidence

Fields:

- recommendation_type
- trust_score
- calibration_error
- effectiveness_score
- supporting_replays
- drift_status

### 8. Operator Outcome

Fields:

- outcome_id
- outcome_type
- actor
- recorded_at
- notes
- recurrence_expected
- followup_required

### 9. Closure State

Fields:

- status
- closed_at
- closure_reason
- next_action
- linked_incident_id

## JSON Skeleton

```json
{
  "evidence_pack_id": "pack-id",
  "generated_at": "timestamp",
  "authority_tag": "v1.2.16-d5b-operator-evidence-path",
  "signal": {},
  "mission_control": {},
  "replay": {},
  "burnin": {},
  "certification": {},
  "trust": {},
  "outcome": {},
  "closure": {}
}
```

## Guardrails

- Evidence Pack v2 must not invent data.
- Missing data must be explicit, not silent.
- Replay/evidence links must preserve run identity.
- Pack generation must not mutate runtime state.
