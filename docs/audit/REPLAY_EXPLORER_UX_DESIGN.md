# Replay Explorer UX Design

> Map backend data contracts to frontend UI panels.
> Generated: 2026-06-01

---

## Backend Data Contract

`GET /api/uar/runs/{run_id}/explorer` returns:

```json
{
  "run_id": "abc-123",
  "summary": {
    "run_id": "abc-123",
    "goal_id": "goal-456",
    "status": "completed",
    "skills": ["doc_ingest", "section_sum"],
    "created_at": "2026-06-01T00:00:00Z"
  },
  "timeline": {
    "events": [...],
    "projections": {...}
  },
  "confidence": {
    "score": 92,
    "tier": "High",
    "warnings": [...]
  },
  "failure_path": [
    { "type": "error", "skill": "math_plot", "error": "..." }
  ],
  "events": [
    { "type": "skill_start", "skill": "doc_ingest", "timestamp": ... },
    ...
  ]
}
```

---

## UI Panel Mapping

### Panel 1 — Run Header (Summary)

| Backend Field | UI Element |
|--------------|-----------|
| `summary.run_id` | Run ID badge (copyable) |
| `summary.status` | Status pill (completed / failed / running) |
| `summary.goal_id` | Goal link (drill-down) |
| `summary.skills` | Skill chips (ordered) |
| `summary.created_at` | Timestamp |
| `confidence.score` | Confidence score ring (0-100) |
| `confidence.tier` | Tier badge (Verified / High / Medium / Low / Failed) |

### Panel 2 — Timeline (Chronological Events)

| Backend Field | UI Element |
|--------------|-----------|
| `events[]` | Vertical timeline with icons per event type |
| `events[].type` | Icon + label (skill_start, skill_end, error, recipe_start, etc.) |
| `events[].skill` | Skill name chip |
| `events[].timestamp` | Relative time ("2s ago") |
| `events[].payload` | Expandable detail accordion |
| `events[].error` | Red error banner inline |

**Event Type Icons:**
- `skill_start` → ▶️
- `skill_end` → ✅
- `recipe_start` → 🍳
- `recipe_end` → 🍳✅
- `error` → ❌
- `retry` → 🔄
- `heartbeat` → 💓 (hidden by default)

### Panel 3 — Confidence Overlay

| Backend Field | UI Element |
|--------------|-----------|
| `confidence.score` | Large score number + color-coded bar |
| `confidence.tier` | Tier badge with description |
| `confidence.warnings[]` | Warning list (severity-colored) |
| `confidence.evidence` | Expandable evidence breakdown |

**Color Coding:**
- Verified (95-100): Green
- High (80-94): Blue
- Medium (60-79): Yellow
- Low (40-59): Orange
- Failed (0-39): Red

### Panel 4 — Failure Path

| Backend Field | UI Element |
|--------------|-----------|
| `failure_path[]` | Filtered timeline showing only error events |
| `failure_path[].error` | Error detail card |
| `failure_path[].skill` | Skill context |
| `failure_path[].timestamp` | Timestamp |

**Empty State:** "No failures detected in this run."

### Panel 5 — Evidence Inspector (Raw Data)

| Backend Field | UI Element |
|--------------|-----------|
| `events[]` | Raw JSON tree (collapsible) |
| `summary` | Key-value table |
| `timeline` | Timeline JSON (for debugging) |

**Tabs:** Summary | Timeline | Events (raw) | Confidence | Failure Path

---

## Component Hierarchy

```
ReplayExplorer
├── RunHeader
│   ├── StatusPill
│   ├── ConfidenceRing
│   └── SkillChips
├── TabNav
│   ├── TimelineTab
│   │   └── EventTimeline
│   │       └── EventCard[]
│   ├── ConfidenceTab
│   │   ├── ScoreDisplay
│   │   ├── TierBadge
│   │   └── WarningList
│   ├── FailurePathTab
│   │   └── ErrorCard[]
│   └── RawDataTab
│       └── JsonTree
└── ActionBar
    ├── Back to Runs
    ├── Replay This Run
    └── Export Report
```

---

## Entry Points

1. **From Mission Control** — Click an active or recent run in the Active Runs list
2. **From Runs History** — Click any historical run in `UARPanel` runs list
3. **Direct URL** — `/explorer/{run_id}` (if router added)

---

## Responsive Behavior

| Viewport | Layout |
|----------|--------|
| Desktop (>1024px) | Sidebar (run list) + Main panel (tabs) |
| Tablet (768-1024px) | Stacked: Header → Tabs → Content |
| Mobile (<768px) | Single column, tabs become dropdown |

---

## Missing Frontend Components (To Build)

| Component | File | Complexity |
|-----------|------|-----------|
| `ReplayExplorer.tsx` | `apps/web/src/components/ReplayExplorer.tsx` | High |
| `EventTimeline.tsx` | `apps/web/src/components/EventTimeline.tsx` | Medium |
| `ConfidenceRing.tsx` | `apps/web/src/components/ConfidenceRing.tsx` | Low |
| `StatusPill.tsx` | `apps/web/src/components/StatusPill.tsx` | Low |
| `JsonTree.tsx` | `apps/web/src/components/JsonTree.tsx` | Medium |
| `EventCard.tsx` | `apps/web/src/components/EventCard.tsx` | Medium |

---

## API Calls Required

```typescript
// Fetch explorer bundle
const explorer = await fetch(
  `/api/uar/runs/${runId}/explorer`,
  { headers: authHeaders() }
)

// Fetch confidence separately (already included in bundle)
const confidence = await fetch(
  `/api/uar/runs/${runId}/confidence`,
  { headers: authHeaders() }
)
```

The explorer bundle already includes confidence, so only **one** API call is needed per run inspection.
