# D4C Roadmap — Fleet Operations

## Status: In Progress (2026-06-05)
**Predecessor:** D4A (Complete), D4B (Complete)  
**Commit Base:** HEAD  
**Objective:** Extend UAR from single-node operational intelligence to multi-node fleet management.

---

## Principle

One UAR instance is an operational intelligence platform.
Many UAR instances, seen together, are a fleet.
The operator should be able to:
- See health across all instances
- Compare analytics between deployments
- Detect fleet-wide patterns (e.g., same skill failing on multiple nodes)
- Route work to the healthiest instance

---

## Approved Work Packages

### D4C-0 — Fleet Heartbeat & Registry
**Priority:** 0 (foundation for all others)

**Problem:** There is no way for a UAR instance to announce itself or for a fleet manager to know which instances exist.

**Solution:**
- `POST /api/uar/fleet/heartbeat` — instances report health snapshot
- `GET /api/uar/fleet/nodes` — list registered instances with last-seen timestamp
- In-memory fleet registry with TTL (nodes expire after 5 min without heartbeat)
- Store fleet state in `uar_metadata` table for persistence across restarts

**Acceptance:**
- Node can heartbeat and be listed
- Stale nodes (no heartbeat > 5 min) are marked offline
- Registry survives restart via `uar_metadata`

**Effort:** Small (1 session)

---

### D4C-1 — Cross-Node Health Dashboard
**Priority:** 1

**Problem:** Mission Control shows only the local node.

**Solution:**
- `GET /api/uar/fleet/health` — aggregate health across all nodes
- Frontend FleetHealthWidget showing:
  - Node grid (name, status, health score, certification level)
  - Fleet-wide alert rollup (critical nodes, consensus failures)
  - Topology overlay (which nodes run which skills)

**Acceptance:**
- Dashboard shows >= 2 nodes with distinct health states
- Clicking a node opens its Mission Control in a new view
- Alerts from any critical node surface in the fleet banner

**Effort:** Medium (1–2 sessions)

---

### D4C-2 — Fleet-Wide Failure Correlation
**Priority:** 2

**Problem:** A skill failing on one node might be a local issue; a skill failing on 5 nodes is a systemic problem.

**Solution:**
- `GET /api/uar/fleet/failures` — aggregate failure clusters across all nodes
- Correlate by skill name + error pattern
- Surface "fleet-wide hotspot" when same skill fails on >= 3 nodes

**Acceptance:**
- Endpoint returns cross-node failure clusters
- Fleet dashboard highlights fleet-wide hotspots
- Drill-down to per-node failure details

**Effort:** Medium (1–2 sessions)

---

### D4C-3 — Skill Routing Hints
**Priority:** 3

**Problem:** The operator manually decides which node handles which workload.

**Solution:**
- `GET /api/uar/fleet/routing` — recommendation for where to run a given goal
- Based on: node health, skill availability, recent failure rate, circuit breaker state
- Returns ranked list of nodes with confidence score

**Acceptance:**
- Routing API returns ranked node list for a given skill/goal
- Top recommendation factors in health + availability + recent success
- Optional `?goal=` parameter for skill-set-aware routing

**Effort:** Medium (1 session)

---

## Deferred

| Item | Reason |
|------|--------|
| Cross-node run migration | Not needed until we have workload orchestration |
| Automatic failover | Requires leader election; out of scope |
| Fleet-wide certification | Complex aggregation; revisit after D4C-2 |

---

## Success Gate

D4C is complete when:
1. [x] D4C-0: Fleet heartbeat and registry operational
2. [x] D4C-1: Cross-node health dashboard visible in frontend
3. [x] D4C-2: Fleet-wide failure correlation surfaces systemic issues
4. [x] D4C-3: Routing hints guide workload placement
5. [x] All tests pass; no regression in single-node behavior

---

## Notes

- Feature freeze lifted 2026-06-05.
- D4C does not change single-node behavior; it adds fleet-layer APIs.
- All fleet APIs are optional — single-node deployments continue to work unchanged.
