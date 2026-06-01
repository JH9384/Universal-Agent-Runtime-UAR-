# Topology Clarification

> Answer: What is topology for?
> Generated: 2026-06-01

---

## The Question

Issue #59 (Topology Visualization v1) and #66 (Runtime Topology Data Service)
propose a topology layer. Before implementation, we must answer:

**Is topology for operator visibility or execution planning?**

## Analysis

### Current State

No topology service exists. No topology code has been written. Issues #59, #60,
#66 are all open and unstarted.

### Option A: Operator Visibility (Mission Control)

**What it would be:**
- A visual graph of the runtime's skill registry
- A per-run execution graph showing which skills ran in what order
- Failed-node highlighting, slow-node highlighting
- "What ran and how did it connect?"

**Evidence supporting this:**
- Mission Control already aggregates operator signals
- Replay Explorer already shows event sequences (a flat timeline, not a graph)
- The operator persona needs to understand runtime structure
- Issue #59's acceptance criteria include "Runtime graph view" and "Run-specific execution graph"

**Where it belongs:** Inside Mission Control as a visualization panel.
**Module:** `apps/web/src/components/TopologyPanel.tsx`
**API:** Thin wrapper around `GET /api/uar/runs/{run_id}/explorer` + skill registry

### Option B: Execution Planning (Runtime Core)

**What it would be:**
- A dependency graph used by the planner to order skills
- Automatic skill sequencing based on input/output dependencies
- Recipe optimization based on graph topology
- "What should run next?"

**Evidence supporting this:**
- Issue #60 (Executor Decomposition) mentions separating orchestration helpers
- The planner currently uses simple linear ordering, not graph-based scheduling
- A topology-aware planner could parallelize independent skills automatically

**Where it belongs:** Inside Runtime Core, near the planner.
**Module:** `uar/core/topology.py`
**API:** Internal, consumed by `SimplePlanner` or successor

## Recommendation

**Both, but in this order:**

1. **Phase 1 — Operator Visibility (Mission Control)**
   - Build a read-only topology view of completed runs
   - Use existing event data to infer the execution graph
   - No new backend service needed — derive from `ReplayExplorer` data
   - This answers the operator's "what happened?" question

2. **Phase 2 — Execution Planning (Runtime Core)** — Deferred
   - Only if the planner becomes graph-aware
   - Requires formal skill I/O contracts (currently implicit)
   - Would enable automatic parallelization
   - This answers the planner's "what should run next?" question

## Decision

**Topology belongs in Mission Control first.**

Reason: The backend already emits all data needed for operator-facing topology
(events, skill registry, run records). The missing piece is purely visualization.
Execution-planning topology would require new skill metadata (inputs, outputs,
dependencies) that does not yet exist.

## Updated Issue Mapping

| Issue | Proposed Resolution |
|-------|-------------------|
| #59 Topology Visualization v1 | Repurpose as Mission Control topology panel |
| #66 Runtime Topology Data Service | Close or defer to Phase 2 |
| #60 Executor Decomposition | Remove topology from scope |

## Implementation Sketch (Phase 1)

```
MissionControlTopologyPanel
├── SkillRegistryGraph (static — all registered skills)
│   └── Nodes = skills, Edges = recipe references
└── RunExecutionGraph (dynamic — per-run)
    └── Nodes = event skills, Edges = event sequence
        └── Color: green (success), red (error), yellow (retry)
```

**No new backend endpoints needed.**
Data sources:
- `GET /api/uar/skills` → registry nodes
- `GET /api/uar/recipes` → recipe edges
- `GET /api/uar/runs/{id}/explorer` → run-specific nodes + edges

---

**Conclusion:** Topology is an operator visibility concern, not a runtime
planning primitive. Build it inside Mission Control. Do not expand the
Runtime Core.
