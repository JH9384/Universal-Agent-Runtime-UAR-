# UAR Development Path (Architectural Control)

This document defines the **clean development path** for UAR so that all technology, UX, and product layers evolve in a controlled, traceable way.

---

# 1. System Layers (Canonical Stack)

## L1 — Core Engine (UAR)
- Object creation
- Execution runtime
- Workflow engine
- Lineage tracking

Status: ✅ Exists
Rule: No UI logic here

---

## L2 — API Abstraction Layer
- Clean functions (no raw endpoints exposed to UI)
- Example:
  - createObject()
  - runAdd()
  - getHistory()

Status: ⚠️ Partial
Action: Standardize wrapper layer

---

## L3 — Experience Layer (Web/Mobile)
- One-screen UI
- No JSON
- No digests
- Tap-driven interaction

Status: ❌ Not complete
Action: Build MVP UI

---

## L4 — Validation Layer
- Tests
- Invariants
- Monte Carlo UX simulation
- Truth Gates

Status: ✅ Strong

---

## L5 — Narrative Layer (Marketing)
- Demo
- Landing page
- Explanation

Status: ⚠️ Emerging

---

# 2. Development Path (Ordered Execution)

## Phase 1 — Stabilize Engine
- All tests pass
- Known limits documented
- No new features

## Phase 2 — Wrap API
- Build clean abstraction layer
- Remove direct API exposure

## Phase 3 — Build UI MVP
- Add numbers
- Run action
- Show result
- Show history

## Phase 4 — User Validation
- Real user test
- Record friction
- Fix UX only

## Phase 5 — UOR Validation
- External object ingestion
- Maintainer review

---

# 3. Tracking System (Required)

All work must map to one of these categories:

| Category | Description |
|--------|------------|
| CORE | Engine functionality |
| API | Wrapper + abstraction |
| UI | User experience |
| TEST | Validation/invariants |
| UOR | Compatibility |
| UX | Friction reduction |
| DOC | Documentation |

---

# 4. Rules of Development

1. No feature without user path
2. No UI exposing internals
3. No claim without test
4. No abstraction without use case
5. Always maintain single demo flow

---

# 5. Current Priority Queue

## P0 (Immediate)
- Build UI MVP (one screen)
- API wrapper stabilization

## P1
- Improve UX based on Monte Carlo results

## P2
- UOR compatibility validation

---

# 6. Definition of “Real”

System is real when:

- A new user completes flow in < 2 minutes
- No explanation required
- Output + lineage understood

---

# 7. Architect Summary

UAR is now:

- Technically valid
- Structurally defined
- Entering product phase

Next risk:

- UX failure

Next success vector:

- Simple interface + real usage
