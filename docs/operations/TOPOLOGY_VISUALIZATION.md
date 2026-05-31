# Topology Visualization

Topology Visualization shows how execution moves through UAR.

It should help operators see:

- where work enters
- where work flows
- where work stalls
- where work fails
- where pressure accumulates

---

## Topology Sources

Topology should be derived from runtime evidence:

- RuntimeEvents
- RunRecords
- Recipe boundaries
- Skill metadata
- Metrics
- Streaming state

No topology view should invent hidden runtime state.

---

## Core Graph

Minimum graph:

```text
Goal
  -> Planner
  -> Strategy
  -> Executor
  -> Skill / Recipe
  -> Event Stream
  -> RunRecord
  -> Replay
```

---

## Node Types

- runtime
- service
- workload
- operation
- external

---

## Edge Types

- plans
- executes
- emits
- persists
- replays
- observes
- depends_on

---

## Operator Views

### Execution Flow

Shows a run moving from goal to terminal result.

### Pressure Map

Highlights queue depth, retry clusters, slow skills, and streaming backlogs.

### Dependency Map

Shows how skills, recipes, stores, caches, and services interact.

### Failure Map

Shows where failures originate and what downstream components were affected.

---

## MVP Requirements

Topology Visualization v1 is complete when operators can:

1. View the high-level UAR runtime graph.
2. View a run-specific execution graph.
3. Identify failed nodes.
4. Identify slow nodes.
5. Export topology as JSON or image.

---

## Safety Rule

Topology Visualization is observer-only.

It must not mutate runtime state or become an execution dependency.
