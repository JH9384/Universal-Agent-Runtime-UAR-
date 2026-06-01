# Issue #87 — Certification Engine Refactor

Status: Open
Priority: P3
Phase: Trust Spine Hardening
Depends on: T1, T2, T3 (all inputs must be Implemented before refactor)

## Problem

`uar/core/certification.py` was built during the construction phase
to accept the full original certification contract including
pressure scores and hardening-era fields that no longer have
corresponding implementations. Specifically:

- `contract_compliance` score input has no producer — it defaults
  to `100` with no real check
- `certification_level()` function signature takes 5 positional args;
  callers pass `has_violations=False` unconditionally
- The 10% weight given to `contract_compliance` is permanently
  inflating scores with a meaningless constant
- `CertificationReport.evidence` dict contains keys (`contract_compliance`,
  `has_violations`) that have no upstream evidence source

## Goal

Refactor `certify_runtime()` and `certification_level()` so that inputs
are exactly the three Trust Spine evidence sources:

| Input | Source | Weight |
|-------|--------|--------|
| replay_confidence_score | T1 ReplayConfidenceReport | 40% |
| burnin_score | T3 BurnInReport | 35% |
| runtime_health_score | T2 RuntimeHealthReport | 25% |

Remove `contract_compliance` entirely.
Remove `has_violations` from the scoring path (may remain as
an advisory field in the report but must not affect the numeric score).

## Proposed Signature

```python
def certify_runtime(
    replay_confidence_score: Optional[int],
    burnin_report: Optional[Any],
    runtime_health_score: Optional[int],
) -> CertificationReport:
    ...
```

Level thresholds (unchanged from current):

- Gold: composite >= 95, replay >= 95, burnin passed, no advisory violations
- Silver: composite >= 80, replay >= 80, burnin completed (any result)
- Experimental: everything else

## Acceptance Criteria

- `certification_level()` no longer accepts `has_violations` as a scoring
  input
- `contract_compliance` removed from `CertificationReport.evidence`
- Weights sum to 100%: replay 40, burnin 35, runtime_health 25
- All existing `test_certification.py` tests updated to match new weights
- New tests verify: weight correctness, no-burnin degrades to Silver max,
  runtime_health=0 cannot reach Gold

## Migration

Callers currently pass `contract_compliance_score` as a keyword argument.
There are none outside the certification module itself (router passes
only `replay_confidence_score`, `burnin_report`, `runtime_health_score`).
No external migration needed.
