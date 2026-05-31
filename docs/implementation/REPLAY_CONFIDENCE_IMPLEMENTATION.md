# Replay Confidence Implementation

## Purpose

Add a pure helper that scores how safely a stored run can be reconstructed from its RuntimeEvent stream.

## Inputs

- RunRecord
- RuntimeEvent list

## Outputs

- confidence level
- numeric score
- warning list
- error list

## Scoring

High confidence:

- event schema is valid
- run starts with start event
- run ends with complete event
- run id is consistent
- goal id is consistent
- timestamps are sane

Medium confidence:

- event stream is valid but has warning-level anomalies

Low confidence:

- partial event stream
- suspicious timestamp or status mismatch

Failed confidence:

- stream cannot be validated or reconstructed

## Suggested Module

`uar/core/replay_confidence.py`

## Suggested API Integration

Add confidence output to:

- `/api/uar/runs/{run_id}/replay`
- future Replay Explorer UI

## Safety

The helper must be pure and must not mutate stored run records.
