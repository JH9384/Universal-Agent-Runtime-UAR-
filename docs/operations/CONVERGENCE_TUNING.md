# UAR Convergence Tuning

Convergence tuning stabilizes runtime behavior under sustained pressure.

## Core Variables

### Pressure
- queue depth
- websocket backlog
- propagation fanout
- mutation rate

### Stability
- oscillation score
- starvation events
- operating-mode transitions
- replay confidence

### Adaptation
- hysteresis thresholds
- observer cadence
- replay compaction
- queue fairness

## Tuning Goals

The runtime should:

- converge smoothly
- avoid oscillation storms
- preserve replay continuity
- prevent starvation
- degrade gracefully

## Operational Guidance

Tune slowly.

Large threshold swings can destabilize the runtime faster than sustained load.

Prefer:
- incremental adjustments
- soak-run validation
- replay validation
- bounded adaptation
