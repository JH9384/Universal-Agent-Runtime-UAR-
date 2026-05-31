# Replay Confidence API Contract

Status: Implemented

Related issues: #74, #75

## Endpoint

GET /api/uar/runs/{run_id}/confidence

## Purpose

Return the Replay Confidence report for a historical run.

This is the first Trust Spine API surface and should be consumed by Mission Control, Replay Explorer, Certification, and Burn-In tooling.

## Response Fields

Top level:

- run_id
- confidence

Confidence fields:

- score
- tier
- warnings
- errors
- dimensions

Dimension fields:

- event_completeness
- timeline_completeness
- store_consistency
- replay_reconstruction_success
- artifact_completeness

## Confidence Tiers

- 95 to 100: Verified
- 85 to 94: High
- 70 to 84: Medium
- 50 to 69: Low
- 0 to 49: Failed

## Warning Codes

Expected warning codes:

- missing_events
- invalid_event_schema
- timeline_gap
- store_record_missing
- store_event_mismatch
- reconstruction_failed
- artifact_missing
- legacy_event_shape
- partial_replay

## Consumers

- Mission Control confidence card
- Replay Explorer confidence overlay
- Certification Scoring
- Burn-In evidence reports
- Runtime Guarantees validation

## Implementation

Core scoring module:

- uar/core/replay_confidence.py

API router:

- uar/api/routers/replay_confidence.py

Router export/mount path:

- uar/api/routers/__init__.py
