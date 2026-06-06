# UAR Freeze and Lock Registry

> Canonical record of all engineering freezes, directional locks, and expansion halts.  
> Last updated: 2026-06-05

---

## Active Freezes

*None. Lifted 2026-06-05 to proceed with D4C — Fleet Operations.*

---

## Historical Freezes (Completed or Lifted)

### 1. Feature Freeze — Ω-7B.1 Operational Validation

| | |
|---|---|
| **Declared** | 2026-06-01 |
| **Lifted** | 2026-06-05 |
| **Status** | **LIFTED** — D4A and D4B complete; freeze no longer necessary. |
| **Scope** | No new runtime capabilities, autonomy layers, or infrastructure expansions |
| **Rationale** | The Trust Spine (T1–T6) is complete. The architecture is rich enough that the next improvements should come from observed behavior rather than design intuition. |
| **Exit criteria** | D4A success gate met (all 6 work packages complete). D4B automation layer operational. |

**Permitted during freeze:**
- Bug fixes and correctness patches
- Instrumentation additions
- Documentation updates
- Dashboard visualizations
- Operational validation tooling

**Deferred (now unblocked):**
- D4C — Fleet Operations

---

### 2. Learning Architecture Freeze v1

| | |
|---|---|
| **Declared** | 2026-06-01 |
| **Lifted** | 2026-06-05 |
| **Status** | **LIFTED** — Feature freeze lifted; learning layers remain stable but not frozen against fleet-context additions. |

**Frozen layers:**

| Layer | Status |
|-------|--------|
| Ω-5.1 Pattern Recognition | Locked |
| Ω-5.2 Feedback Collection | Locked |
| Ω-5.3 Quality Metrics | Locked |
| Ω-5.4 Adaptive Confidence | Locked |
| Ω-5.5 Outcome Attribution | Locked |
| Ω-6a Effectiveness Intelligence | Locked |
| Ω-6b Calibration Intelligence | Locked |
| Ω-6c Replay Intelligence | Locked |
| Ω-7a Trust Computation | Locked |
| Ω-7b Trust-Aware Ranking | Locked |

**Not frozen:**
- Bug fixes
- Instrumentation additions
- Documentation updates
- Dashboard visualizations
- Operational validation tooling

---

## Historical Freezes (Completed)

### 3. Trust Spine Construction Freeze

| | |
|---|---|
| **Declared** | 2026-05-15 |
| **Lifted** | 2026-05-31 |
| **Status** | Complete — all phases operational |
| **Scope** | Capability expansion frozen until Trust Spine milestones were complete |
| **Rationale** | Capability Atlas audits showed infrastructure maturity exceeded trust maturity. No new subsystems until trust primitives were operational. |

**Deferred during freeze:**
- Parallel executor expansion
- Replay timeline UI
- Richer orchestration intelligence
- Advanced graph animation
- Production database backends beyond JSONL
- Marketplace systems
- Agent economy systems
- Workflow studio expansion

**Exit criteria met:**
- T1 Replay Confidence operational
- T2 Runtime Health operational
- T3 Burn-In Framework operational
- T4 Certification Engine operational
- T5 Mission Control operational
- T6 Replay Explorer operational

---

### 4. Hardening Phase Freeze

| | |
|---|---|
| **Declared** | 2026-05-31 |
| **Lifted** | 2026-06-01 |
| **Status** | Complete — transitioned to Operational Intelligence Platform |
| **Scope** | No new Trust Spine phases, concepts, layers, or subsystems |
| **Rationale** | Trust Spine was built; hardening focused on performance, persistence, correctness, and observability before declaring completion. |

**Permitted during hardening:**
- Performance (query consolidation, caching)
- Persistence (burn-in store, report durability)
- Correctness (ownership, concurrency, error paths)
- Observability (structured logging, metrics)

**Hardening backlog (all resolved):**
- ~~#85~~ Runtime Health Query Consolidation — resolved
- ~~#86~~ Burn-In Persistence Layer — resolved
- ~~#87~~ Certification Engine Refactor — resolved

---

## Directional Locks

### 5. Issue #83 — Runtime Health Contract & Scoring Engine

| | |
|---|---|
| **Locked** | 2026-05-15 |
| **Status** | Complete — T2 Runtime Health operational |
| **Scope** | Directional lock: all engineering effort aligned to the Trust Spine until it was complete |
| **Rationale** | Execution exists to generate evidence. Evidence exists to establish trust. Trust exists to support operations. |

**Path:** Execution → Evidence → Trust → Operations → Analytics → Search → Insight

---

## Decision Matrix

| Condition | Action |
|-----------|--------|
| All Ω-7B.1 exit criteria met | Proceed to Ω-7c Trust Visibility |
| Trust distribution compressed | Investigate formula weights |
| No resolution correlation | Extend burn-in or adjust evidence_component |
| High drift without detection | Tighten drift_penalty threshold |
| Ranking thrashes | Increase evidence gate before trust applies |

---

## Enforcement

These freezes are **binding engineering policy**, not advisory notes.

### Violation Checklist

Before any PR is merged during an active freeze, the author must confirm:

- [ ] No new components, layers, or subsystems are introduced
- [ ] No new learning logic is added (during Learning Architecture Freeze)
- [ ] No new dependencies are added without explicit freeze-exemption review
- [ ] All changes are listed in one of: bug fix, instrumentation, documentation, visualization, or validation tooling
- [ ] `docs/FREEZES_AND_LOCKS.md` is updated if the freeze boundary changes

### Exemption Process

If a change genuinely requires violating an active freeze:

1. Open a dedicated issue titled `[Freeze Exemption] <brief description>`
2. Tag it with the freeze name (e.g., `freeze:feature-freeze-v1`)
3. Document: what, why, why it cannot wait, and what validation will be performed
4. Require two approvals before merge

No exemptions have been granted since 2026-06-01.

---

## Key Principle

The most valuable commit may not be Ω-7a or Ω-7b.

It may be the commit that says:

**STOP BUILDING. START MEASURING.**

Because that's the point where the system begins teaching you something back.
