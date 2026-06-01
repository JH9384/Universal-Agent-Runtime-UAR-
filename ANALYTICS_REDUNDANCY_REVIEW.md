# Analytics Redundancy Review

## UAR Analytics Review — Audit B
**Scope:** Identify duplicate, overlapping, or redundant metrics across the analytics layer  
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Status:** Complete

---

## Methodology

For each metric type, we ask:
1. Where does it appear?
2. Is it computed from the same source data?
3. Is the presentation meaningfully different (different question answered)?
4. Classification: Intentional / Accidental / Candidate Consolidation

---

## Metric: Failure Count

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `MissionControlWidget` | `recent_warnings.length` | Warnings count (not failures) |
| `ReplayExplorer` (Summary tab) | `failure_path.length` | Failures for a single run |
| `CompareRuns` | `_analyze()` diff | Failure delta between two runs |
| `FailureClusterPanel` | `Store.list_records` scan | Total failures across N runs + top skills + error patterns |
| `ConfidenceDriftPanel` | `Store.list_records` scan | `failure_summary.total_failures` + top skill breakdown |
| `FailureHotspotPanel` | `Store.list_records` scan | Total failures + node/edge failure rates |

### Analysis
- **Three different scopes:** Single-run (`ReplayExplorer`), Pair-wise (`CompareRuns`), Aggregate (`FailureClusterPanel`, `ConfidenceDriftPanel`, `FailureHotspotPanel`).
- **Aggregate overlap:** `FailureClusterPanel` and `FailureHotspotPanel` both do full-table scans of the same time window to count failures by skill. `ConfidenceDriftPanel` also counts failures by skill for its "Top Contributors" section.
- **Same computation, different grouping:**
  - ClusterPanel → groups by (skill, error_message)
  - HotspotPanel → groups by (skill, transition) with severity
  - DriftPanel → groups by (skill) for contributors only

### Classification
| Pair | Verdict |
|------|---------|
| FailureClusterPanel ↔ FailureHotspotPanel | **Candidate Consolidation** — Same source data, same time window. One groups by error message, the other by topology. Could be merged into a single endpoint with two views. |
| FailureClusterPanel ↔ ConfidenceDriftPanel | **Accidental Redundancy** — Both count `skill_failures` from the exact same scan. DriftPanel only uses top 5 for contributors; ClusterPanel returns top 10. |
| FailureHotspotPanel ↔ ConfidenceDriftPanel | **Accidental Redundancy** — DriftPanel's `failure_summary.top_skills` is a subset of what HotspotPanel computes. |

---

## Metric: Confidence Score

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `MissionControlWidget` | `build_snapshot()` | Score + tier ring |
| `TrendPanel` | `_MC_HISTORY` | Score sparkline over time |
| `ConfidenceDriftPanel` | `_MC_HISTORY` | Previous vs Current vs Delta |
| `ReplayExplorer` | `score_replay()` | Score + tier + warnings for single run |
| `CompareRuns` | `score_replay()` x2 | Confidence delta between runs |
| `RecipeIntelligencePanel` | `run.confidence` | Avg confidence per recipe |

### Analysis
- **Mission Control, Trends, and Drift all read from `_MC_HISTORY`.** This is intentional — MC produces the snapshots, Trends and Drift consume them.
- **Replay Explorer and Compare Runs compute confidence per-run.** This is correct and non-redundant because they answer a different question ("What was this run's confidence?" vs "What is the system's confidence right now?").
- **RecipeIntelligencePanel** uses the same per-run confidence but aggregates by recipe. This is a distinct derived metric.

### Classification
| Pair | Verdict |
|------|---------|
| TrendPanel ↔ ConfidenceDriftPanel | **Intentional Redundancy** — Both read `_MC_HISTORY` confidence scores but answer different questions (trend shape vs delta magnitude). |
| MissionControlWidget ↔ TrendPanel | **Intentional** — MC shows current snapshot; Trends shows history. |
| All aggregate confidence sources | **Intentional** — Each answers a distinct scope question. |

---

## Metric: Success / Failure Rate

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `TopologyAnalyticsPanel` | `Store.list_records` | Per-skill success rate, per-edge success rate, per-recipe success rate |
| `FailureHotspotPanel` | `Store.list_records` | Per-skill failure rate, per-edge failure rate |
| `RecipeIntelligencePanel` | `Store.list_records` | Per-recipe success rate, failure rate |
| `BurnInHistory` | `_BURNIN_HISTORY` | Pass rate across burn-in runs |

### Analysis
- **TopologyAnalyticsPanel and FailureHotspotPanel are complementary views of the same data.** One shows "how often does this succeed?" the other shows "how often does this fail?" They are mathematically linked (`failure_rate = 1 - success_rate` for nodes, approximately).
- **RecipeIntelligencePanel and TopologyAnalyticsPanel both show recipe success rate.** They compute it from the same source (`metadata.execution_order` + run status).

### Classification
| Pair | Verdict |
|------|---------|
| TopologyAnalyticsPanel ↔ FailureHotspotPanel | **Candidate Consolidation** — Two endpoints scanning the same runs to compute inverse metrics. Could be a single `/topology/analytics` endpoint with `?view=success` or `?view=failure` param. |
| TopologyAnalyticsPanel (recipes) ↔ RecipeIntelligencePanel | **Accidental Redundancy** — Both compute `recipe.success_rate` from the same `execution_order` metadata. Intelligence panel adds classification and avg_confidence/avg_duration. Could merge recipe section from TopologyAnalytics into Intelligence. |

---

## Metric: Recipe Utilization / Executions

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `TopologyAnalyticsPanel` | `metadata.execution_order` | Recipe executions + success rate |
| `RecipeIntelligencePanel` | `metadata.execution_order` | Recipe executions + success rate + classification |

### Analysis
- **Identical source, identical base metric, different presentation.** TopologyAnalytics shows recipes in a table alongside skills and edges. RecipeIntelligence classifies them into Recommended/Monitor/Retire.

### Classification
| Pair | Verdict |
|------|---------|
| TopologyAnalyticsPanel (recipes) ↔ RecipeIntelligencePanel | **Candidate Consolidation** — The recipe table in TopologyAnalytics is a strict subset of what RecipeIntelligence computes. Removing the recipe section from TopologyAnalytics and linking to RecipeIntelligence would eliminate duplication. |

---

## Metric: Skill Invocation / Usage

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `TopologyAnalyticsPanel` | `run.skills` list | Invocations count, success rate |
| `FailureHotspotPanel` | `run.skills` list | Invocations count, failure rate |
| `FailureClusterPanel` | `events` with errors | Failure count per skill |
| `ReplayExplorer` | `run.skills` list | Skills used in single run |
| `CompareRuns` | `run.skills` list | Skills added/removed between runs |

### Analysis
- **TopologyAnalytics and FailureHotspotPanel both count skill invocations** from the same `run.skills` list in the same time window. One shows success context, the other failure context.
- **FailureClusterPanel also breaks down by skill** but from `events` rather than `run.skills`. For failed runs these should converge, but for runs where a skill errors without being in `run.skills`, they diverge.

### Classification
| Pair | Verdict |
|------|---------|
| TopologyAnalyticsPanel ↔ FailureHotspotPanel | **Candidate Consolidation** — Same source, same metric, complementary sign (success vs failure). Mergable. |
| FailureClusterPanel ↔ Topology/Hotspot | **Intentional** — ClusterPanel derives from events (more granular), while Topology derives from `run.skills` (coarser). Both are useful but should be documented as distinct. |

---

## Metric: Burn-In Score / Evidence

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `MissionControlWidget` | `certification.evidence.burnin_score` | Current burn-in score + pass/fail |
| `BurnInHistory` | `_BURNIN_HISTORY` | Score trend + pass rate + avg score |

### Analysis
- **Mission Control shows the latest snapshot.** BurnInHistory shows the trend. These are intentionally complementary.

### Classification
| Pair | Verdict |
|------|---------|
| MissionControlWidget ↔ BurnInHistory | **Intentional** — Point-in-time vs time series. Correct separation. |

---

## Metric: Recent Warnings

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `MissionControlWidget` | `build_snapshot()` | `recent_warnings` list (up to 5) |
| `ReplayExplorer` | `score_replay()` | Per-run warnings |

### Analysis
- **Different scopes.** MC shows system-wide recent warnings; Replay Explorer shows warnings for a specific run.

### Classification
| Pair | Verdict |
|------|---------|
| MissionControlWidget ↔ ReplayExplorer | **Intentional** — System vs single-run. No redundancy. |

---

## Metric: Total Runs / Runs Scanned

### Appearances
| Component | Source | What is shown |
|-----------|--------|-------------|
| `FailureClusterPanel` | `Store.list_records` | `total_runs_scanned` |
| `FailureHotspotPanel` | `Store.list_records` | `total_runs` |
| `TopologyAnalyticsPanel` | `Store.list_records` | `total_runs` |
| `RecipeIntelligencePanel` | `Store.list_records` | `total_runs` |

### Analysis
- **Every aggregate endpoint reports the denominator.** This is good practice for context, not redundancy.

### Classification
| Observation | Verdict |
|-------------|---------|
| All panels show denominator | **Intentional** — Context required for rate interpretation. |

---

## Redundancy Summary Table

| Redundancy | Components | Severity | Recommendation |
|------------|------------|----------|----------------|
| Failure counting (aggregate) | FailureClusterPanel, FailureHotspotPanel, ConfidenceDriftPanel | **High** | Merge Cluster + Hotspot into single endpoint with `?groupby=` param. Drift should consume it rather than re-scan. |
| Recipe success rate | TopologyAnalyticsPanel, RecipeIntelligencePanel | **Medium** | Remove recipe table from TopologyAnalytics. Link to RecipeIntelligence. |
| Skill invocations | TopologyAnalyticsPanel, FailureHotspotPanel | **Medium** | Merge into single topology analytics endpoint with `?mode=success\|failure`. |
| Full-table scan pattern | All 5 aggregate endpoints | **High** | Introduce materialized cache or indexed query. Every aggregate endpoint independently scans all runs. |
| MC History dependency | TrendPanel, ConfidenceDriftPanel | **Low** | Intentional. But document that these require MC polling to be useful. |

---

## Candidate Consolidation Plan

### Option 1: Merge Topology Analytics (Minimal Change)

```
/api/uar/topology/hot-paths       → keep (success view)
/api/uar/topology/failure-hotspots → DEPRECATE, fold into hot-paths?mode=hotspots
/api/uar/runs/failure-clusters     → keep (error-message grouping is distinct)
/api/uar/confidence-drift          → keep, but stop internal re-scanning
                                     consume /failure-clusters for contributors
```

### Option 2: Single Analytics Endpoint (Larger Change)

```
GET /api/uar/analytics?type=failures&groupby=skill|error|topology&hours=24
GET /api/uar/analytics?type=topology&mode=success|failure&hours=168
GET /api/uar/analytics?type=recipes&hours=168
GET /api/uar/analytics?type=drift&hours=24
```

This would reduce 5 full-table-scan endpoints to 1 router + parameterized logic.

### Recommendation

**Adopt Option 1 for the next maintenance cycle.** It requires no frontend routing changes and reduces the worst overlap (Topology ↔ Hotspot). Option 2 should be prototyped during D4 planning if the performance baseline (Audit D) confirms scan overhead is a bottleneck.

---

## Metrics That Are NOT Redundant (Documented for Clarity)

- **Runtime Health** — Only appears in MissionControlWidget. Unique metric.
- **Certification** — Only appears in MissionControlWidget. Unique metric.
- **Active Runs** — Only appears in MissionControlWidget. Unique metric.
- **Replay Timeline** — Only appears in ReplayExplorer. Unique view.
- **Skill Diff (added/removed)** — Only appears in CompareRuns. Unique metric.
- **Burn-In Trend** — Only appears in BurnInHistory. Unique view.
- **Recipe Classification** — Only appears in RecipeIntelligencePanel. Unique derived metric.

---

## Next Steps

- Proceed to **Review C — Operator Journey**
- Proceed to **Review D — Performance Baseline**
