# D4 Direction Proposal

## UAR Analytics Review — Audit E
**Scope:** Synthesize A–D into a recommended next phase  
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Status:** Complete

---

## Executive Summary

**Recommendation: D4A — Operational Optimization**

The audit evidence does not support beginning D4B (Autonomous Operations) or D4C (Fleet Management) at this time. The next bottleneck is not "what the system should do automatically" or "how to manage many UARs." The next bottleneck is **how efficiently the current analytics layer answers operator questions at scale**.

Specifically:
- **Performance:** Aggregate endpoint latency grows linearly with dataset size. At 10,000 runs, the heaviest endpoint takes ~280ms per request. With the default 1,000-run cap removed, this becomes ~700ms at 100k runs.
- **Redundancy:** Five aggregate endpoints independently scan the same data. Two topology endpoints compute inverse metrics from the same source. Recipe data appears in two panels with overlapping logic.
- **Operator Experience:** Mission Control renders nine panels as a single scrollable wall. There is no progressive disclosure, no alert surfacing, and no direct navigation from an aggregate finding to the specific run that caused it.

These are optimization problems, not autonomy or fleet problems.

---

## Evidence from Each Audit

### Audit A — Dependency Matrix

**Finding:** Every aggregate endpoint (`failure-clusters`, `confidence-drift`, `hot-paths`, `failure-hotspots`, `recipes/intelligence`) performs an independent full-table scan. There is no shared cache, materialized view, or aggregation layer between the store and the API.

**Implication:** Each request repeats the same I/O and computation. This is the root cause of the linear latency growth observed in Audit D.

### Audit B — Redundancy Analysis

**Finding:**
- `TopologyAnalyticsPanel` and `FailureHotspotPanel` scan identical data to compute complementary metrics (success rate vs failure rate).
- `FailureClusterPanel` and `ConfidenceDriftPanel` both count skill-level failures from the same event stream.
- `RecipeIntelligencePanel` and `TopologyAnalyticsPanel` (recipe section) both derive recipe success rate from `metadata.execution_order`.

**Implication:** The operator sees the same underlying computation presented in three different ways. This creates cognitive load without adding information.

### Audit C — Operator Journey

**Finding:**
- Analytics are modal-based and secondary to the execution interface.
- Mission Control embeds all 9 sub-panels unconditionally.
- There is no automatic surfacing of critical findings (e.g., "critical hotspot detected").
- There is no direct link from aggregate findings to individual run replays.

**Implication:** The operator must manually hunt for signals. The system explains execution but does not guide the operator toward what needs attention.

### Audit D — Performance Baseline

**Finding:**
- Mission Control: 0.19ms → 279.68ms (10 → 10,000 runs)
- Failure Clusters: 0.18ms → 282.77ms
- Topology Analytics: 0.22ms → 306.15ms
- Recipe Intelligence: 0.20ms → 284.63ms
- Replay Explorer: effectively 0ms at all scales

**The database layer is not the bottleneck.** SQLite returns 10,000 rows in <10ms. The latency is entirely Python-side JSON deserialization and dictionary manipulation.

**Implication:** Optimization must focus on reducing per-request computation, not database tuning.

---

## Why Not D4B (Automation) or D4C (Fleet)

### D4B — Autonomous Operations

Candidate features:
- Automatic burn-in scheduling
- Automatic regression detection
- Automatic certification re-evaluation

**Why not now:**
- Automation requires reliable, fast analytics as its input signal. If the confidence drift computation takes 280ms and is only available on-demand, the system cannot efficiently evaluate whether a re-run is needed.
- The current analytics are read-only summaries. There is no action API to invoke even if the system decided action was warranted.
- Before teaching the system to "act," the evidence layer it acts upon must be fast, deduplicated, and always available.

### D4C — Fleet Operations

Candidate features:
- Multiple runtime monitoring
- Cross-deployment analytics
- Fleet-wide topology

**Why not now:**
- The user assessment is correct: fleet operations are theoretical today.
- The repository is architected as a single-runtime operational intelligence platform.
- All performance and redundancy findings are local to a single SQLite-backed instance. Fleet operations would introduce distributed systems complexity before the local analytics layer is optimized.

---

## Proposed D4A Work Packages

### D4A.1 — Materialized Analytics Cache (Highest Priority)

**Problem:** Every aggregate request re-computes from raw records.

**Solution:** Introduce an in-memory TTL cache keyed by `(endpoint, user_id, hours_window, top_limit)`.

**Implementation sketch:**
- Add `_ANALYTICS_CACHE: dict` in `mission_control.py` or a new `uar/core/analytics_cache.py`.
- TTL default: 60 seconds.
- Cache invalidation: explicit on `append()` or TTL expiry.
- Expected impact: reduce aggregate latency from ~280ms to <5ms at all scales.

**Effort estimate:** Small (1–2 sessions).

---

### D4A.2 — Endpoint Consolidation (High Priority)

**Problem:** `TopologyAnalyticsPanel` and `FailureHotspotPanel` are separate endpoints scanning the same data.

**Solution:** Merge `/api/uar/topology/hot-paths` and `/api/uar/topology/failure-hotspots` into a single `/api/uar/topology/analytics` endpoint with `?mode=success|failure` parameter.

**Also:** Remove the recipe table from `TopologyAnalyticsPanel` and link to `RecipeIntelligencePanel` instead.

**Effort estimate:** Small (1 session).

---

### D4A.3 — Progressive Disclosure in Mission Control (Medium Priority)

**Problem:** Mission Control renders all 9 panels unconditionally.

**Solution:** Add tabbed sections:
- Health (score rings, component health, burn-in)
- Trends (TrendPanel, ConfidenceDriftPanel)
- Failures (FailureClusterPanel, FailureHotspotPanel)
- Topology (TopologyWidget, TopologyAnalyticsPanel)
- Intelligence (RecipeIntelligencePanel)

**Effort estimate:** Small (1 session).

---

### D4A.4 — Alert Banner in UARPanel (Medium Priority)

**Problem:** Critical findings are buried inside Mission Control.

**Solution:** Surface the single highest-severity finding as a dismissible banner in `UARPanel`:
- "Critical hotspot: `riscv` → `verilog` failure rate 60% — open Mission Control"
- "Confidence degrading: -12 points in last 24h — open Mission Control"

**Effort estimate:** Small (1 session).

---

### D4A.5 — Direct Run Links from Aggregate Panels (Medium Priority)

**Problem:** `FailureClusterPanel` shows `latest_error` but no link to the run that produced it.

**Solution:** Include the `run_id` of the latest error in the cluster response and render it as a link to `ReplayExplorer`.

**Effort estimate:** Tiny (< 1 session).

---

### D4A.6 — Document or Remove the 1,000-Run Cap (Low Priority)

**Problem:** `list_records(limit=1000)` silently truncates aggregate analytics.

**Solution:** Either:
- Raise the default limit for analytics endpoints, or
- Add `"runs_analyzed": N` to every aggregate response so operators understand the scope, or
- Document the cap in the API and UI.

**Effort estimate:** Tiny (< 1 session).

---

## Implementation Order

| Priority | Work Package | Deliverable |
|----------|--------------|-------------|
| 1 | D4A.1 | Materialized cache + performance regression test |
| 2 | D4A.2 | Consolidated topology endpoint + frontend update |
| 3 | D4A.3 | Tabbed Mission Control layout |
| 4 | D4A.4 | Alert banner in UARPanel |
| 5 | D4A.5 | Run links in FailureClusterPanel |
| 6 | D4A.6 | Cap documentation |

---

## Success Criteria for D4A

1. **All aggregate endpoints respond in <10ms at 10,000 runs** (with cache warm).
2. **No two panels compute the same metric independently** unless they answer different questions.
3. **Mission Control provides progressive disclosure** — operator sees summary first, details on demand.
4. **Critical findings surface without requiring manual panel navigation**.
5. **Operator can traverse from aggregate finding to specific run replay in one click**.

---

## Future Decision Gate

After D4A is complete, re-run Audits A–D. If:
- Performance is flat (<10ms) regardless of dataset size,
- Redundancy is eliminated,
- Operator journey is guided rather than hunted,

**Then** evaluate D4B (Automation) or D4C (Fleet) based on actual operational need, not architectural momentum.

---

## Conclusion

UAR has crossed the threshold from "observe execution" to "explain it." The next phase must ensure it explains execution **efficiently, concisely, and at scale** before it attempts to act on those explanations autonomously or distribute them across a fleet.

**D4A — Operational Optimization** is the evidence-based next step.
