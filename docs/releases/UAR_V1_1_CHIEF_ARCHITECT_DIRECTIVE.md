# UAR v1.1 Chief Architect Directive

## Status

Architecture Freeze v1.1 is ACTIVE.

UAR is to be treated as a Universal Execution Runtime.

Directional Lock: Issue #83 (Runtime Health Contract)

---

## Trust Formula

```text
Execution -> Evidence -> Trust -> Operations
```

Execution generates evidence. Evidence establishes trust. Trust supports operations.

---

## Canonical Plan

The authoritative documents for v1.1 are:

| Document | Authority |
| --- | --- |
| `docs/releases/UAR_V1_1_OPERATIONAL_RUNTIME_ROLLOUT.md` | Sprint sequence, release checklist, certification gates |
| `docs/TRUST_SPINE.md` | Phase definitions, directional lock, T1–T6 architecture |
| `docs/V1_1_EXECUTION_PLAN.md` | Issue-linked execution sequence |

These three documents are co-authoritative. In case of conflict, `TRUST_SPINE.md` and the directional lock from Issue #83 take precedence.

The Operational Runtime Rollout is the source of truth for:

- sprint planning
- certification gates
- burn-in requirements
- release checklist
- release criteria

The Trust Spine is the source of truth for:

- priority order
- phase definitions
- directional constraints

---

## Prime Directive

The purpose of v1.1 is not to make UAR smarter.

The purpose of v1.1 is to make UAR trustworthy.

---

## Architecture Freeze

Locked contracts:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Workload Contract v1
- Runtime Boundary Audit

No major redesigns are authorized during v1.1.

---

## Operating Rule

Every pull request must answer:

"Does this make UAR a more trustworthy execution runtime?"

If the answer is no, defer it until after v1.1 certification.
