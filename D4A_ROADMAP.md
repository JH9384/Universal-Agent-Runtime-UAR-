# D4A Roadmap — Operational Optimization

## Phase D4A
**Status:** Approved (2026-06-01)  
**Objective:** Reduce duplication, reduce latency, increase operator actionability  
**Commit Base:** 57ed78b  
**Predecessor:** Phase D (Operational Analytics) + Audit Reviews A–E  
**Successor:** TBD — D4A must complete and re-audit before D4B or D4C evaluation

---

## Principle

UAR does not need more capability right now.
It needs its existing capability to be:
- Cheaper (cached, not re-computed)
- Clearer (deduplicated, well-named)
- Easier to act upon (alerted, linked, not hunted)

---

## Approved Work Packages

### D4A-0 — Resolve 1,000-Run Cap
**Priority:** 0 (before all others)  
**Why:** Hidden limits become operational surprises. The system must declare its boundaries.

**Decision:** Remove the `limit=1000` default for analytics endpoints, or expose `runs_analyzed` in every aggregate response so the operator understands scope.

**Acceptance:**
- `list_records` called by analytics endpoints does not silently truncate.
- Every aggregate response includes `runs_analyzed` and `total_runs`.
- No operator can be surprised that analytics "missed" older data.

**Effort:** Tiny (< 1 session)

---

### D4A-1 — Materialized Analytics Cache
**Priority:** 1  
**Why:** Highest ROI. Every panel benefits.

**Problem:** Every aggregate request re-scans and re-aggregates raw run records.

**Solution:** In-memory TTL cache keyed by `(endpoint, user_id, hours_window, top_limit)`.

**Acceptance:**
- Aggregate endpoint median latency < 10 ms at 10,000 runs (cache warm).
- Cache invalidates on `append()` or TTL expiry (default 60s).
- Cache is transparent; no frontend changes required.

**Effort:** Small (1–2 sessions)

---

### D4A-2 — Endpoint Consolidation
**Priority:** 2  
**Why:** Eliminate duplicated scans.

**Problem:** `/api/uar/topology/hot-paths` and `/api/uar/topology/failure-hotspots` scan the same runs to compute inverse metrics. Recipe data appears in both Topology Analytics and Recipe Intelligence.

**Solution:**
- Merge topology endpoints into `/api/uar/topology/analytics?mode=success|failure`.
- Remove recipe table from Topology Analytics; link to Recipe Intelligence.

**Acceptance:**
- One topology endpoint serves both views.
- Frontend updated to use consolidated endpoint.
- No loss of information.

**Effort:** Small (1 session)

---

### D4A-3 — Alert Banner
**Priority:** 3  
**Why:** Operators should see critical signals without scrolling through Mission Control.

**Problem:** Critical findings (hotspots, confidence collapse, certification degradation) are buried inside a modal.

**Solution:** Dismissible banner in `UARPanel` that surfaces the highest-severity finding from Mission Control.

**Acceptance:**
- Banner appears when severity exceeds a threshold.
- One-click dismiss.
- Clicking the banner opens Mission Control.
- Supported alert types: critical hotspot, confidence degrading, certification degradation.

**Effort:** Small (1 session)

---

### D4A-4 — Deep Linking
**Priority:** 4  
**Why:** Close the loop: Alert → Cluster → Replay in one click.

**Problem:** `FailureClusterPanel` shows `latest_error` but provides no path to the run that produced it.

**Solution:** Include `run_id` in cluster/hotspot responses and render as a link to `ReplayExplorer`.

**Acceptance:**
- Every failure cluster row includes a clickable run ID.
- Clicking it opens `ReplayExplorer` for that run.
- Same for failure hotspot nodes/edges where a specific run is the latest contributor.

**Effort:** Tiny (< 1 session)

---

### D4A-5 — Progressive Disclosure Tabs
**Priority:** 5  
**Why:** Mission Control is now large enough that showing everything is worse than showing the important things first.

**Problem:** Mission Control renders 9 panels as a single scrollable wall.

**Solution:** Tabbed sections:
- Health (score rings, component health, burn-in)
- Trends (TrendPanel, ConfidenceDriftPanel)
- Failures (FailureClusterPanel, FailureHotspotPanel)
- Topology (TopologyWidget, TopologyAnalyticsPanel)
- Intelligence (RecipeIntelligencePanel)

**Acceptance:**
- Default tab is Health (the current top-of-page experience).
- Tab state persists per session.
- No panel is removed; only organized.

**Effort:** Small (1 session)

---

## Deferred Work

| Phase | Status | Reason |
|-------|--------|--------|
| D4B — Automation | Deferred | Requires fast, reliable analytics as input signal. D4A must complete first. |
| D4C — Fleet Operations | Deferred | Theoretical today. No operational need demonstrated. |

---

## Success Gate

D4A is complete when:

1. [ ] D4A-0: 1,000-run cap resolved and documented.
2. [ ] D4A-1: All aggregate endpoints < 10 ms at 10,000 runs (cache warm).
3. [ ] D4A-2: Topology endpoints consolidated; no duplicate scans.
4. [ ] D4A-3: Alert banner surfaces critical findings in UARPanel.
5. [ ] D4A-4: Failure cluster/hotspot rows link directly to Replay Explorer.
6. [ ] D4A-5: Mission Control uses tabbed progressive disclosure.
7. [ ] Re-run Audit A–D and confirm all findings are resolved or accepted.

Only then evaluate D4B or D4C.

---

## Audit Artifacts

- `ANALYTICS_DEPENDENCY_MATRIX.md` — Review A
- `ANALYTICS_REDUNDANCY_REVIEW.md` — Review B
- `OPERATOR_JOURNEY_REVIEW.md` — Review C
- `PERFORMANCE_BASELINE.md` — Review D
- `D4_DIRECTION_PROPOSAL.md` — Review E
- `audit_benchmark.py` — Benchmark script
- `D4A_ROADMAP.md` — This document

---

## Notes

- Feature freeze remains in effect until D4A success gate is met.
- The benchmark script should be preserved and re-run after D4A-1 and D4A-2 to verify improvement.
