# Operator Journey Review

## UAR Analytics Review — Audit C
**Scope:** Map how an operator navigates the analytics layer  
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Status:** Complete

---

## Methodology

Trace the actual UI state transitions and entry points from the main panel (`UARPanel.tsx`) and the `MissionControlWidget` layout. There is no client-side router (React Router); navigation is modal-based with boolean flags.

---

## Entry Points

### Primary Entry: UARPanel Main UI

The main operator interface is `UARPanel.tsx`. It presents:
- Goal input + skill selection
- Execution order builder
- Run trigger + event log
- **Bottom toolbar buttons** that open analytics modals

Relevant toolbar buttons (from `UARPanel.tsx`):
- `Runs History` → opens `showRunsPanel` modal
- `Mission Control` → opens `showMissionControl` modal
- `Health Dashboard` → opens `showHealthDashboard` modal
- `Replay` (per run) → opens `showReplayExplorer` modal
- `Compare` (from Runs History) → opens `showCompareRuns` modal

### Secondary Entry: Mission Control Widget

`MissionControlWidget.tsx` is a **compound dashboard** that embeds all remaining analytics panels inline:
- `ConfidenceDriftPanel`
- `TrendPanel`
- `BurnInHistory`
- `FailureClusterPanel`
- `TopologyWidget`
- `TopologyAnalyticsPanel`
- `FailureHotspotPanel`
- `RecipeIntelligencePanel`

There is **no separate navigation** to these panels. They are always visible when Mission Control is open.

---

## Journey Map

### Intended Flow (Inferred from UI Structure)

```
UARPanel (execution view)
    │
    ├──► Runs History (list of past runs)
    │       │
    │       ├──► Replay Explorer (single-run deep dive)
    │       │       │
    │       │       ├── Summary → Status, skills, events, failures
    │       │       ├── Timeline → Event sequence
    │       │       ├── Confidence → Replay confidence score + warnings
    │       │       ├── Failure Path → Error events only
    │       │       └── Events → Raw JSON
    │       │
    │       └──► Compare Runs (two-run diff)
    │               │
    │               ├── Metrics → Confidence / Events / Failures delta
    │               └── Skills → Added / Removed / Failed
    │
    └──► Mission Control (system-wide dashboard)
            │
            ├── Score Rings → Health / Confidence / Certification (current)
            ├── Mini Cards → Active Runs / System Health / Burn-In / Warnings
            ├── Component Health → Per-component breakdown
            ├── Confidence Drift → Delta + contributors + failure correlation
            ├── Trends → 24h sparklines
            ├── Burn-In History → Score trend + pass rate
            ├── Failure Clusters → Top skills + error patterns
            ├── Topology Widget → Skill registry + recipe edges (static)
            ├── Topology Analytics → Hot paths + transitions + recipe usage
            ├── Failure Hotspots → Dangerous skills + transitions
            └── Recipe Intelligence → Recommended / Monitor / Retire
```

---

## Actual Journey Assessment

### What is the FIRST thing an operator sees?

The main `UARPanel` is the default view. It is **execution-oriented**, not analytics-oriented. Analytics are accessed through toolbar buttons or embedded in Mission Control.

**Finding:** Analytics are secondary to the execution interface. There is no dedicated analytics landing page.

### What causes ACTION?

| Trigger | Likely Action |
|---------|--------------|
| `FailureClusterPanel` shows a skill with high failure count | Operator opens `ReplayExplorer` for a failed run |
| `ConfidenceDriftPanel` state = "degrading" | Operator checks `TrendPanel` for when decline started, then `FailureClusterPanel` for cause |
| `RecipeIntelligencePanel` shows "retire" classification | Operator stops using that recipe in the execution order |
| `FailureHotspotPanel` shows critical edge | Operator reorders skills or changes recipe composition |
| `BurnInHistory` shows declining score | Operator triggers new burn-in run or inspects recent runs |

**Finding:** The analytics layer successfully closes the loop back to execution. Every panel can drive a change in the execution order or skill selection.

### What causes CONFUSION?

| Issue | Location | Reason |
|-------|----------|--------|
| Trends panel empty | `TrendPanel` | Requires MC snapshots to be collected. If operator never opens MC, no history exists. |
| Drift panel empty | `ConfidenceDriftPanel` | Same dependency on MC history. |
| Topology Widget vs Topology Analytics | `MissionControlWidget` | Two panels with similar names. One is static registry, the other is execution-derived. |
| Failure Clusters vs Failure Hotspots | `MissionControlWidget` | Both show failures. One by error message, one by topology. Names do not clarify the distinction. |
| Recipe Intelligence vs Topology Analytics (recipes) | `MissionControlWidget` | Both show recipe success rate. One classifies, one just lists. |

**Finding:** The embedded panel layout in Mission Control places all analytics on one long scrollable page. There is no visual hierarchy distinguishing "primary signal" from "secondary detail."

---

## Routing and State Analysis

### Modal State Management (UARPanel)

| State | Default | Trigger | Dismiss |
|-------|---------|---------|---------|
| `showRunsPanel` | `false` | "Runs History" button | Close button or overlay click |
| `showMissionControl` | `false` | "Mission Control" button | Close button or overlay click |
| `showHealthDashboard` | `false` | "Health Dashboard" button | Close button or overlay click |
| `showReplayExplorer` | `false` | "Explore" from Runs History | Close button or overlay click |
| `showCompareRuns` | `false` | "Compare" from Runs History | Close button or overlay click |

### Modal State Management (MissionControlWidget)

Mission Control is itself a modal overlay. All sub-panels are **always rendered inline** when it is open. There is no sub-navigation within Mission Control.

**Finding:** Mission Control is a "wall of analytics." There is no progressive disclosure. An operator opening Mission Control receives 9 panels simultaneously.

---

## Panel Ordering Within Mission Control

From `MissionControlWidget.tsx` (line 198-222):

```
1. ConfidenceDriftPanel
2. TrendPanel
3. BurnInHistory
4. FailureClusterPanel
5. TopologyWidget
6. TopologyAnalyticsPanel
7. FailureHotspotPanel
8. RecipeIntelligencePanel
```

Preceded by:
- Score rings (Health, Confidence, Certification)
- Mini cards (Active Runs, System Health, Burn-In, Warnings)
- Component health grid

**Assessment:** The ordering is logical: drift → trends → burn-in → failures → topology → hotspots → intelligence. But without progressive disclosure, an operator must scroll through all panels to find the signal relevant to their current concern.

---

## Entry Point Frequency (Code-Inferred)

| Feature | Entry Condition | Frequency |
|---------|-----------------|-----------|
| Mission Control | Button click | On-demand |
| Runs History | Button click | On-demand |
| Replay Explorer | "Explore" click from Runs History | Per-run |
| Compare Runs | "Compare" click from Runs History | Per-pair |
| Health Dashboard | Button click | On-demand |

**Finding:** All analytics are on-demand. None are pushed. There are no alerts, notifications, or automatic redirections to analytics when a run fails.

---

## Gaps in the Journey

1. **No "You have a critical hotspot" entry point.** If `FailureHotspotPanel` would classify a skill as "critical," there is no mechanism to surface this without the operator manually opening Mission Control.

2. **No direct link from FailureClusterPanel to ReplayExplorer.** The panel shows "latest_error" strings but does not provide a clickable run ID to open that run's Replay Explorer.

3. **No bookmarkable analytics state.** Since all navigation is modal-based boolean state, refreshing the page loses the operator's current analytic view.

4. **No progressive disclosure.** Mission Control renders all 9 sub-panels unconditionally. On a slow connection or large dataset, this is expensive.

5. **Trends and Drift dependency on MC polling is hidden.** The empty-state copy explains this, but only after the operator already opened the panel and saw nothing.

---

## Recommendations

### Short Term (No new features)

1. **Document the MC history dependency** in panel empty states. The existing copy says "History builds as Mission Control snapshots are collected" — this is good but could be more explicit: "Open Mission Control to begin collecting snapshots."

2. **Rename or clarify Topology Widget vs Topology Analytics.** Suggest: "Skill Registry" (static) and "Execution Topology" (derived).

3. **Add run_id links in FailureClusterPanel.** When a cluster row shows `latest_error`, also show the run_id it came from, linked to ReplayExplorer.

### Medium Term (During D4 planning)

4. **Add tabs or accordion to Mission Control.** Group panels into:
   - Health (Score rings, Component health, Burn-In)
   - Trends (TrendPanel, ConfidenceDrift)
   - Failures (FailureClusterPanel, FailureHotspotPanel)
   - Topology (TopologyWidget, TopologyAnalyticsPanel)
   - Intelligence (RecipeIntelligencePanel)

5. **Introduce a lightweight alert banner** in UARPanel that surfaces the highest-severity signal from Mission Control without opening it (e.g., "1 critical hotspot detected — open Mission Control").

---

## Next Steps

- Proceed to **Review D — Performance Baseline**
