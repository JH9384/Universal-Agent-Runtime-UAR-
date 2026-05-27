# UAR Runtime Certification

Runtime certification validates survivability and replay integrity under pressure.

## Certification Categories

### Pressure Stability
- queue depth
- websocket backlog
- topology pressure
- propagation fanout

### Replay Integrity
- replay confidence
- divergence score
- reconstruction completeness
- continuity preservation

### Runtime Survivability
- operating-mode transitions
- starvation resistance
- oscillation stability
- degradation behavior

### Long-Horizon Stability
- soak-run survivability
- memory drift
- convergence stability
- reconnect recovery

## Certification Outputs

Burn-in runs should produce:

- operational artifacts
- telemetry traces
- runtime health snapshots
- replay summaries
- convergence reports

## Operational Goal

The runtime should degrade gracefully before violating causality, replay identity, or event legality.
