# Ω-5 Charter — Operational Learning

**Repository:** Universal Agent Runtime (UAR)  
**Phase:** Ω-5  
**Branch:** `omega-5-learning`  
**Baseline:** `omega-4-complete` (91 tests passing)  
**Date:** 2026-06-01  
**Status:** INITIATED

---

## Objective

Ω-1 through Ω-4D established:

- Trust (Ω-2)
- Provenance (Ω-4A)
- Memory (Ω-4B)
- Governance (Ω-4C)
- Observation (Ω-4D)

Ω-5 adds the first genuinely new capability:

> **Adaptation**

The system begins to use its accumulated knowledge rather than merely storing it.

---

## The Missing Layer

Current lifecycle:

```
Events
  ↓
Replay
  ↓
Provenance
  ↓
Memory
  ↓
Governance
```

Ω-5 completes the loop:

```
Events
  ↓
Replay
  ↓
Provenance
  ↓
Memory
  ↓
Governance
  ↓
Recommendation
  ↓
(Action → new Events)
```

---

## Four Tracks

### Ω-5A — Recommendation Engine

**Question:** Given operational memory, what should the operator consider?

**Inputs:**
- Recurring failure patterns (Ω-4B)
- Recovery atlas (Ω-4B)
- Governance trends (Ω-4C)
- Topology evolution (Ω-4B)

**Outputs:**
- Prioritized recommendation list
- Confidence scores
- Action categories (investigate, optimize, review, remediate)

**Examples:**
- "timeout::skill_a+skill_b recurred 8 times. Consider increasing timeout."
- "Topology node 'hot_skill' growing 2x faster than others. Investigate load."
- "Certification failure rate spiked 15% this week. Review recent changes."

---

### Ω-5B — Recovery Advisor

**Question:** Given a failure, what recovery action has succeeded before?

**Inputs:**
- Failure signature
- Recovery atlas (Ω-4B)
- Historical recovery success rates

**Outputs:**
- Ranked recovery suggestions
- Expected success probability
- Time-to-recovery estimate

**Example:**
- "timeout::skill_a+skill_b: 73% of recoveries succeeded with retry."

---

### Ω-5C — Governance Insights

**Question:** What governance trends demand attention?

**Inputs:**
- Governance record history (Ω-4C)
- Approval rate trends
- Tampered detection rates
- Recurring failure rates

**Outputs:**
- Trend alerts
- Review queue prioritization
- Retention policy recommendations

**Examples:**
- "Approval rate dropped 20% this month. Review workload."
- "Tampered detection rate stable at 7%. No action needed."
- "3 governance records pending review > 7 days. Escalate."

---

### Ω-5D — Topology Optimization Signals

**Question:** Where is the topology becoming unhealthy?

**Inputs:**
- Topology evolution timeline (Ω-4B)
- Node/edge growth rates
- Hot region history

**Outputs:**
- Growth anomaly alerts
- Cold region recommendations (unused skills)
- Hot region capacity warnings

**Examples:**
- "Node count grew 3x in 7 days. Investigate skill proliferation."
- "Edge 'skill_a -> skill_b' is cold (0 invocations). Consider deprecation."

---

## Success Criteria

Ω-5 succeeds when:
1. Recommendations are generated automatically from operational memory
2. Recovery suggestions are ranked by historical success rate
3. Governance trends produce actionable alerts
4. Topology signals identify optimization targets
5. All recommendations include confidence scores
6. The system remains certified (all Ω-2 through Ω-4 tests pass)

---

## Key Principle

> **Not machine learning. Operational learning.**

Ω-5 uses the structured data already collected by Ω-4:
- Recurrence patterns
- Recovery paths
- Governance summaries
- Topology evolution

It applies simple, explainable heuristics:
- Frequency ranking
- Success rate weighting
- Threshold alerting
- Trend comparison

The recommendations are transparent and auditable — not black-box predictions.

---

## Current Maturity Model

| Phase | Status |
|-------|--------|
| Construction | ✅ |
| Audit (Ω-1) | ✅ |
| Certification (Ω-2) | ✅ |
| Validation (Ω-3) | ✅ |
| Provenance (Ω-4A) | ✅ |
| Multi-Run Intelligence (Ω-4B) | ✅ |
| Governance (Ω-4C) | ✅ |
| Extended Deployment (Ω-4D) | ✅ |
| **Recommendation Engine (Ω-5A)** | **⏳ IN PROGRESS** |
| Recovery Advisor (Ω-5B) | ⏳ |
| Governance Insights (Ω-5C) | ⏳ |
| Topology Signals (Ω-5D) | ⏳ |

---

## Immediate Priority

**Ω-5A Recommendation Engine** is the lead track.

It directly leverages the operational memory from Ω-4B and produces the first actionable output from accumulated history.

---

## Architecture Extension

```
Operational Memory (Ω-4B)
        ↓
Recommendation Engine (Ω-5A)
        ↓
Governance Record (Ω-4C)  [updated with recommendations]
        ↓
Operator Dashboard
```

The recommendation engine sits between memory and governance, enriching records with suggested actions before they reach the operator.
