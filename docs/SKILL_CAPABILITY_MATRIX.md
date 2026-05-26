# Skill Capability Governance Matrix

## Purpose

This document defines the operational governance dimensions used by the UAR runtime.

The matrix is intended to evolve into generated operational runtime visibility.

---

# Governance Dimensions

## Maturity

```text
stable
beta
experimental
stub
deprecated
```

## Side Effects

```text
PURE
LOCAL_WRITE
NETWORK_WRITE
EXTERNAL_MUTATION
DESTRUCTIVE
```

## Replay Safety

```text
ReplaySafe
ReplayConditional
ReplayUnsafe
```

## Observability Levels

```text
minimal
standard
verbose
```

---

# Operational Expectations

| Governance Area | Purpose |
|---|---|
| Maturity | operational confidence + deployment gating |
| Side Effects | replay legality + orchestration legality |
| Replay Safety | deterministic replay certification |
| Observability | runtime auditability + diagnostics |
| Resource Requirements | future scheduling + runtime isolation |

---

# Replay Governance

Replay certification should reject:

- replay drift
- unsafe deterministic guarantees
- replay-unsafe side effects
- schema incompatibility
- event ordering divergence

---

# Strategic Direction

UAR orchestration expansion should occur only after:

- replay determinism hardening
- SkillContract enforcement
- side-effect governance stabilization
- replay safety certification

Runtime guarantees must dominate orchestration complexity.
