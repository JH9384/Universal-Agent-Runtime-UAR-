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

## Phase 7B — D4C Operator Loop Release Gate

Required if promoting the D4C fleet/operator/recurrence/evidence spine:

- [ ] `make d4c-release-gate` passes
- [ ] D4C validation result is captured under `docs/operations/validation-results/` or CI artifact exists
- [ ] Mission Control still exposes `fleet_summary`
- [ ] Mission Control still exposes `incident_summary`
- [ ] Briefing and Focus surface fleet or recurrence context
- [ ] Replay handoff works from Briefing, Focus, and recurrence
- [ ] Outcome capture still uses `/api/uar/recommendations/outcome`
- [ ] Artifacts still surfaces Evidence Pack preview
- [ ] Evidence Markdown copy/download works
- [ ] Anti-sprawl criteria confirmed: no incident console, no incident store, no duplicate endpoint, no new dashboard, no second trust score, no parallel evidence pipeline

Reference docs:

- `docs/operations/D4C_RELEASE_READINESS_SUMMARY.md`
- `docs/operations/D4C_RELEASE_PROMOTION_CHECKLIST.md`
- `docs/operations/D4C_RELEASE_NOTES_DRAFT.md`

## Phase 8 — Final Review

- [ ] PR size acceptable OR split into slices
- [ ] CI consistently green across multiple runs
- [ ] No unexpected logs, warnings, or crashes

## Gate

Only proceed to merge when ALL above are satisfied.
