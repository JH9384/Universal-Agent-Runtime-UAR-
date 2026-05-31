# UAR Burn-In Procedure

Burn-in validates that UAR behaves predictably under sustained, repeated, and stressful operation.

## Purpose

Burn-in is not feature testing.

Burn-in answers:

- Does the runtime remain stable over time?
- Does replay remain valid after long execution windows?
- Do metrics stay bounded?
- Do streaming connections degrade?
- Do retries, cache, and coalescing behave under pressure?

---

## Burn-In Levels

### Level 1: Smoke Burn-In

Duration: short local run

Validates:

- API starts
- core run executes
- events emit
- run persists
- timeline endpoint works

### Level 2: Soak Burn-In

Duration: multi-hour repeated workloads

Validates:

- stable event counts
- bounded memory
- no replay regression
- stable skill latency
- predictable retry behavior

### Level 3: Pressure Burn-In

Duration: controlled high-load session

Validates:

- queue behavior
- websocket stability
- rate limit behavior
- cache behavior
- failure containment

### Level 4: Certification Burn-In

Duration: release-candidate validation window

Validates:

- replay fidelity
- event integrity
- runtime health score
- certification report generation
- operator diagnosability

---

## Required Artifacts

Every certification burn-in should produce:

- run summary
- runtime health summary
- replay confidence summary
- event integrity summary
- failure-path summary
- certification result

---

## Pass Criteria

A burn-in passes when:

- all runs have replayable event streams
- no unbounded queue growth occurs
- no unexplained websocket collapse occurs
- event schema violations are zero or explicitly accepted
- runtime health stays within accepted limits
- certification report is generated

---

## Fail Criteria

A burn-in fails when:

- run reconstruction fails
- terminal events are missing
- event schema drift appears
- retry storms occur
- cache/coalescing corrupts output consistency
- runtime cannot explain a failure path

---

## Operational Rule

No new major feature class should be added during burn-in hardening unless it directly improves observability, replay, certification, or runtime safety.
