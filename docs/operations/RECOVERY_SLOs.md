# Ω-3C Recovery SLOs

**Repository:** Universal Agent Runtime (UAR)  
**Phase:** Ω-3 Real World Validation — Track C  
**Branch:** `omega-3-validation`  
**Baseline:** `omega-2-certified` (111 certification tests passing)

---

## Objective

Define and measure formal Service Level Objectives for recovery behavior.

Ω-2 proved correctness under normal operation. Ω-3C measures how quickly the system returns to correct operation after disruption.

---

## SLO Definitions

### Detection

| SLO | Target | Measurement | Rationale |
|-----|--------|-------------|-----------|
| SLO-D1 Failure Detection | < 5s | Time from error injection to alert surfacing | Operator must know something is wrong |
| SLO-D2 Replay Certification Fail | < 100ms | `certify_replay()` returns `fidelity_score=0` | Corruption must be instant |
| SLO-D3 Cache Miss Detection | < 1s | Analytics endpoint returns stale vs fresh data | Stale data must not persist |

### Recovery

| SLO | Target | Measurement | Rationale |
|-----|--------|-------------|-----------|
| SLO-R1 Cache Rebuild | < 30s | `build_analytics_snapshot()` after `invalidate()` | Fresh data must be quickly available |
| SLO-R2 Replay Load | < 2s | Click to `replay_loaded` event | Evidence must be fast to access |
| SLO-R3 Snapshot Refresh | < 5s | New run → updated analytics panels | Operators see current state |
| SLO-R4 Topology Recovery | < 60s | Node loss → topology still renders | Degradation must not be fatal |
| SLO-R5 Burn-In Recovery | < 10s | Failure → next burn-in attempt succeeds | Certification must self-heal |

### Consistency

| SLO | Target | Measurement | Rationale |
|-----|--------|-------------|-----------|
| SLO-C1 Post-Recovery Fidelity | 100% | `certify_replay()` after any recovery | Recovery must not corrupt data |
| SLO-C2 Post-Recovery Cache | Consistent | All panels derive from same snapshot | No split-brain after rebuild |
| SLO-C3 Post-Recovery Topology | Consistent | Node/edge counts match expected | Topology state remains valid |

---

## Measurement Method

Each SLO is measured via pytest with `time.perf_counter()`:

```python
def test_slo_r1_cache_rebuild():
    # 1. Populate cache
    cache.set(...)
    # 2. Invalidate
    t0 = time.perf_counter()
    cache.invalidate()
    # 3. Rebuild
    build_analytics_snapshot(runs, ...)
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0
```

---

## Violation Handling

An SLO violation is **not** a certification failure. It is an observation.

The response is:
1. Log the violation in `REAL_WORLD_VALIDATION_LOG.md`
2. Compare to Ω-2 baseline predictions
3. Decide: expected degradation, unexpected regression, or new limit discovered
4. Document the decision

---

## Baseline vs Target

| SLO | Ω-2 Baseline | Ω-3 Target | Notes |
|-----|-------------|-----------|-------|
| SLO-D1 | N/A (no failure injection) | < 5s | New measurement |
| SLO-D2 | 100ms (certification test) | < 100ms | Already certified |
| SLO-R1 | < 1s (burn-in tests) | < 30s | Relaxed under load |
| SLO-R2 | < 2s (MC-2 test) | < 2s | Already certified |
| SLO-R3 | < 5s (cache tests) | < 5s | Already certified |
| SLO-R4 | < 10s (topology tests) | < 60s | Relaxed under extreme scale |
| SLO-C1 | 100% (C3 tests) | 100% | Must never degrade |

**SLO-C1 is non-negotiable.** If recovery ever produces `fidelity_score < 100%` on valid data, that is a certification regression and must be investigated immediately.

---

## Sign-off

| Gate | Status |
|------|--------|
| SLOs defined | ✅ Complete |
| Measurement method documented | ✅ Complete |
| Baseline vs target established | ✅ Complete |
| Violation handling defined | ✅ Complete |
| Tests implemented | ⏳ Pending |
| Targets verified | ⏳ Pending |

