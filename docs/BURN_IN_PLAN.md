# UAR Burn-In Plan

## Objective

Make execution truth undeniable. Then build intelligence around it later.

This is an **operational validation campaign**, not feature development.

---

## Phase 0 — Lock Scope

**NO:**
- new planners
- new skills
- new observers
- DSE overlays
- semantic evaluators
- cognition layers
- symbolic overlays
- multi-agent logic
- persistence rewrites
- speculative UI

**ONLY:**
- validation
- replay proving
- certification
- timeline verification
- contract tightening
- instrumentation hardening

---

## Phase 1 — Environment Baseline

**Actions:**

1. Verify branch state:
   ```
   git status
   make version
   make sync-version
   git diff -- VERSION pyproject.toml
   ```
   Expected: no unexpected drift.

2. Install clean environment:
   ```
   python -m pip install -e '.[dev]'
   ```

---

## Phase 2 — Core Runtime Validation

### Path 2A — Planner Validation

```
pytest tests/test_planner_router.py -q
```

Validates:
- deterministic routing
- fail-closed invalid modes
- explicit LLM opt-in

**Rule:** Do NOT add planner features. Only tighten routing, config validation, error semantics.

### Path 2B — RuntimeConfig Validation

```
pytest tests/test_runtime_config.py -q
```

Validates:
- invalid ports rejected
- invalid persistence rejected
- timeout semantics stable
- planner mode enforcement stable

### Path 2C — RuntimeEvent Validation

```
pytest tests/test_runtime_events.py -q
```

Validates:
- schema stability
- event builder correctness (`make_executor_event`)
- metadata separation
- enum semantics

---

## Phase 3 — Replay Integrity Burn-In

### Path 3A — Replay Integrity

```
pytest tests/test_replay_integrity.py -q
```

Validates:
- RuntimeEvent trace → RunRecord reconstruction
- deterministic reconstruction
- stable event ordering
- proper lifecycle enforcement

### Path 3B — Timeline Projection

```
pytest tests/test_timeline.py -q
```

Validates:
- RuntimeEvent trace → Timeline projection
- stable chronology
- stable indexing
- stable summary metrics

---

## Phase 4 — Fixture Replay Certification

### Path 4A — Runtime Trace Fixtures

```
pytest tests/test_runtime_trace_fixtures.py -q
```

Validates canonical traces:
- `runtime_trace_success.json`
- `runtime_trace_failure.json`

Expected: fixture → replay → timeline → summary remains stable.

### Path 4B — Replay Certification

```
pytest tests/test_replay_certification.py -q
```

Validates trace normalization:
- timestamps
- correlation IDs
- generated IDs

Expected: **semantic equivalence**, NOT literal equality.

---

## Phase 5 — Executor Migration Burn-In

**Status: COMPLETE**

`make_executor_event(...)` created in `uar/core/executor.py`.
Legacy `_event(...)` delegates to it for backward compatibility.

No execution logic, event ordering, or payload structure was changed.

---

## Phase 6 — Full Gate Burn-In

```
make gate
```

Runs:
- `pytest tests/ -q --tb=short` (full backend suite)
- `ruff check uar/ tests/`
- `pytest tests/test_runtime_*.py`
- `pytest tests/test_replay_*.py`
- `pytest tests/test_timeline.py`

**Burn-In Iterations:** Repeat run → inspect → tighten → rerun. Minimum 5–10 clean iterations before merge consideration.

---

## Phase 7 — Timeline UI Seed

**Status: PENDING**

Build ONLY after substrate is stable:
- Run Header
- Timeline
- Details Drawer
- Summary

**NO:** cognition overlays, semantic maps, DSE, observer scoring, symbolic recursion, swarm views.

---

## Phase 7B — Learning Operational Validation (Ω-7B.1)

**Status:** ACTIVE — All tooling production-ready. Data accumulation in progress.

**Scope:** Validate the trust and learning subsystem before it becomes a
primary decision signal.

**Prerequisites:**
- Ω-7a Trust Computation — implemented and verified
- Ω-7b Trust-Aware Ranking — implemented (feature-flagged off)
- Operator dashboard — displays trust scores, divergence alerts, component bars
- Outcome→Trust pipeline — verified end-to-end via `cache_validation.py`

**Verified Pipeline:**
```
Outcome → Effectiveness → Trust → Mission Control
```
Confirmed by `scripts/hardening/cache_validation.py`.

Note: `min_samples=5` in effectiveness computation means trust scores
emerge only after 5+ outcomes per category. This is healthy — trust should
require evidence, not a single success.

**Collection Schedule:**

**Daily:**
```bash
python scripts/hardening/divergence_investigation.py --output reports/divergence/$(date +%Y%m%d).json
```
Captures high-confidence/low-trust and low-confidence/high-trust outliers.

**Weekly:**
```bash
./scripts/hardening/run_trust_validation.sh
```
Archives full trust metrics to `reports/trust_validation/`.

**Continuous (staged):**
```bash
# Stage 1: 24h
python scripts/hardening/long_duration_burnin.py --duration 24h

# Stage 2: 72h (only after 24h passes cleanly)
python scripts/hardening/long_duration_burnin.py --duration 72h

# Stage 3: 168h (only after 72h passes cleanly)
python scripts/hardening/long_duration_burnin.py --duration 168h
```

**Four Metrics:**
- **Trust Distribution** — Are scores naturally spread across bands?
- **Ranking Delta** — Where do confidence and trust disagree?
- **Outcome Correlation** — Does higher trust → higher resolution?
- **Drift Discovery** — Any high-trust types with negative drift?

**Exit Criteria:**
- Trust scores vary by < 0.10 week-over-week for established types
- Calibration bucket errors vary by < 0.05 week-over-week
- Top-5 trust types remain consistent
- Spearman correlation(trust, resolution_rate) >= 0.3 (minimum), 0.5 (preferred)

**Duration:** 2–4 weeks or sufficient recommendation volume.

**Next Milestone:** Trust Validation Report #1

See `docs/operations/LEARNING_MODEL.md` § Ω-7B.1 for full details.

## Phase 8 — Merge Readiness Review

Review:
- `SYSTEM.md`
- `CONFORMANCE.md`
- `docs/BURN_IN_PLAN.md`

Expected:
- no scope drift
- deterministic-first posture
- RuntimeEvents as execution truth
- other-side modules externalized

---

## Success Criteria

Burn-in completes when:
- [ ] `make gate` passes repeatedly
- [ ] replay tests remain stable
- [ ] certification tests remain stable
- [ ] fixture traces replay deterministically
- [ ] timeline projections remain stable
- [ ] executor migration preserves traces
- [ ] docs remain coherent
- [ ] no feature creep occurred

---

## Final Burn-In Target

At the end of this phase UAR should confidently be:

**A deterministic, event-oriented, replayable execution substrate.**

**NOT yet:**
- a cognition platform
- a semantic runtime
- a DSE engine
- a symbolic orchestration layer
- a swarm environment

Those attach later.
