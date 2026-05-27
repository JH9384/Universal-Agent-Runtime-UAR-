# UAR Mission Control

Mission Control is the operational visibility layer for UAR.

The goal is not decorative dashboards.
The goal is runtime observability, survivability analysis, and replay-aware operational management.

## Core Panels

### Runtime Health
- pressure score
- oscillation score
- replay confidence
- starvation alerts
- operating mode

### Topology
- propagation fanout
- partition detection
- queue congestion
- node isolation

### Replay
- divergence scoring
- reconstruction confidence
- continuity timeline
- replay archaeology

### Burn-In
- soak-run history
- trend forecasting
- survivability traces
- operational artifacts

## Design Principles

Mission Control must remain:

- bounded
- pressure-aware
- observer-safe
- low-latency
- operationally calm
- deterministic where possible

The observer layer may never destabilize the runtime.
