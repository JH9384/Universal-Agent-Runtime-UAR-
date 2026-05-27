# Operational Layer Support Guidance

The operational layer exists to expose runtime survivability without destabilizing the runtime.

## Core Operational Supports

### Runtime Health
- bounded telemetry cadence
- replay-safe updates
- observer throttling
- pressure-aware batching

### Replay
- deterministic reconstruction
- continuity preservation
- divergence surfacing
- replay archaeology

### Topology
- partition visibility
- pressure hotspots
- queue congestion awareness
- propagation tracing

### Burn-In
- soak-run retention
- artifact indexing
- convergence history
- survivability reporting

## UI Discipline

The operational layer should:
- feel calm
- remain readable under pressure
- avoid visual overload
- degrade gracefully
- prioritize operational truth over visual novelty

## Runtime Discipline

Operational tooling may never:
- amplify websocket pressure
- create render storms
- starve runtime queues
- violate replay continuity
- bypass degradation rules
