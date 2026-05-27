# Live Telemetry Session Guidance

Live telemetry sessions validate Mission Control against real runtime conditions.

## Session Goals

Validate:
- runtime health continuity
- replay synchronization
- websocket survivability
- bounded telemetry cadence
- observer-safe rendering
- topology visibility

## Session Rules

Telemetry systems must:
- throttle deterministically
- compact under pressure
- preserve replay continuity
- preserve operational calm

## Validation Targets

### Runtime
- operating-mode transitions
- starvation visibility
- oscillation tracking
- pressure stability

### Replay
- continuity preservation
- divergence visibility
- reconstruction integrity

### UI
- bounded rendering
- stable timeline virtualization
- topology pressure visibility
- artifact synchronization

## Outputs

Sessions should produce:
- replay summaries
- telemetry traces
- convergence histories
- survivability artifacts
- certification reports
