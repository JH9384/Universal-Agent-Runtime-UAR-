# Runtime Health

Runtime Health measures whether UAR is operating within safe and predictable execution boundaries.

## Health Domains

### Execution

Track:

- active runs
- queued runs
- completion rate
- failure rate
- retry rate

### Skills

Track:

- skill latency
- skill failures
- skill starvation
- skill throughput

### Event System

Track:

- events per second
- event loss detection
- schema violations
- replay consistency

### Streaming

Track:

- websocket connections
- disconnect frequency
- stream latency
- stream backlog

### Runtime Pressure

Track:

- queue depth
- execution backlog
- contention indicators
- resource pressure

## Runtime Health Score

Suggested composite:

- 25% execution
- 20% skills
- 20% events
- 15% streaming
- 20% pressure

Range:

100 = nominal
75+ = healthy
50+ = degraded
25+ = unstable
0-25 = critical

## Operator Goals

Operators should detect:

- backlog formation
- replay degradation
- starvation
- retry storms
- topology partitions

before user-visible failures occur.
