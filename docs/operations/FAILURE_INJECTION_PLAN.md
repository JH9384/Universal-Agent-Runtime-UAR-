# Ω-3B Failure Injection Plan

**Repository:** Universal Agent Runtime (UAR)  
**Phase:** Ω-3 Real World Validation — Track B  
**Branch:** `omega-3-validation`  
**Baseline:** `omega-2-certified` (111 certification tests passing)

---

## Objective

Prove recovery rather than correctness.

Ω-2 proved the system is correct. Ω-3B proves the system **recovers** when correctness is intentionally disrupted.

---

## Injection Matrix

| ID | Failure | Injection Point | Expected Outcome | Recovery Metric |
|----|-----------|-----------------|------------------|-----------------|
| FI-1 | Websocket disconnect | Frontend → API socket | Automatic reconnect | reconnect_ms |
| FI-2 | Cache purge (forced) | `ANALYTICS_CACHE.invalidate()` | Fresh rebuild | rebuild_ms |
| FI-3 | Replay stream corruption | Event stream tampered | Certification fails loudly | detection_ms |
| FI-4 | Missing topology node | Synthetic run with unknown skill | Graceful skip | degradation_ratio |
| FI-5 | Interrupted run | No `complete` event in stream | EventContractError | error_surface_ms |
| FI-6 | Partial event loss | Drop middle event from stream | Certification fail (hash mismatch) | detection_ms |
| FI-7 | Duplicate terminal event | Append extra `complete` event | EventContractError | detection_ms |
| FI-8 | Store write failure (transient) | `put_metadata` error | Retry or degrade gracefully | recovery_ms |
| FI-9 | Snapshot build under extreme memory | 100k+ node topology | Completes without crash | build_ms |
| FI-10 | Concurrent burn-in + analytics | Simultaneous operations | Cache consistency maintained | consistency_check |

---

## Test Structure

Each injection test follows:

```python
def test_fi_<id>_<name>():
    # 1. Establish certified baseline state
    # 2. Inject failure
    # 3. Measure detection time
    # 4. Measure recovery time
    # 5. Verify state consistency
    # 6. Log observation
```

---

## Pass Criteria

| Failure Class | Detection Target | Recovery Target |
|---------------|-----------------|-----------------|
| Transient (FI-1, FI-2, FI-8) | < 1s | < 5s |
| Data Integrity (FI-3, FI-6, FI-7) | < 100ms | N/A (fail loud) |
| Structural (FI-4, FI-5) | < 1s | Graceful degradation |
| Resource (FI-9) | N/A | Completes within 2× baseline |
| Concurrency (FI-10) | < 1s | State remains consistent |

---

## Success Definition

Ω-3B passes when:

1. All 10 injections execute without crashing the runtime
2. Detection times meet targets
3. Recovery times meet targets
4. State after recovery matches certified baseline expectations
5. `fidelity_score` remains 100% for valid data after every recovery

---

## Risk

Failure injection on a production system is dangerous. These tests must run:
- On the `omega-3-validation` branch
- Against isolated test stores
- With synthetic data only
- Never against live operator sessions

---

## Sign-off

| Gate | Status |
|------|--------|
| Injection tests defined | ⏳ Pending |
| Detection measured | ⏳ Pending |
| Recovery measured | ⏳ Pending |
| State consistency verified | ⏳ Pending |

