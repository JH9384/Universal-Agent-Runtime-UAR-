# UAR Production Release Checklist

## Phase 1 — CI Stabilization

- [ ] All foundation pytest tests pass
- [ ] No flaky or timing-dependent failures
- [ ] Streaming tests deterministic

## Phase 2 — Execution Integrity

- [ ] No duplicate execution in streaming path
- [ ] `/run` and `/stream` produce equivalent final outputs
- [ ] Replay reconstruction matches execution output

## Phase 3 — Contract Lock

- [ ] RuntimeEvent schema version frozen (`uar.event.v1`)
- [ ] No missing required fields in events
- [ ] TS contracts match Python contracts

## Phase 4 — Build Hygiene

- [ ] Python dependencies pinned or consciously accepted
- [ ] Node dependencies pinned (no "latest")
- [ ] Reproducible install confirmed locally

## Phase 5 — Documentation

- [ ] SYSTEM.md complete and accurate
- [ ] API usage documented
- [ ] Local run instructions verified

## Phase 6 — Security Pass (Basic)

- [ ] Input validation present on API routes
- [ ] No arbitrary code execution vectors
- [ ] Safe skill execution boundaries

## Phase 7 — Release Slice Decision

Choose one:

- [ ] Option A: Runtime + API + Streaming + Replay (UI staged)
- [ ] Option B: Extract slices (core, API, replay, UI)

## Phase 8 — Final Review

- [ ] PR size acceptable OR split into slices
- [ ] CI consistently green across multiple runs
- [ ] No unexpected logs, warnings, or crashes

## Gate

Only proceed to merge when ALL above are satisfied.
