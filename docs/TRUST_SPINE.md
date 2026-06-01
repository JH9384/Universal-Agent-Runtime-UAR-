# UAR Trust Spine Architecture Baseline

Status: Active  
Release Target: v1.1 Trust Release

## Prime Directive

UAR v1.1 is not about making the runtime smarter.

UAR v1.1 is about making the runtime trustworthy.

## Architectural Principle

Execution exists to generate evidence.

Evidence exists to establish trust.

Trust exists to support operations.

## Directional Lock

Locked in Issue #83 (RuntimeHealthReport Contract & Scoring Engine).

```text
Execution -> Evidence -> Trust -> Operations
```

Execution generates evidence. Evidence establishes trust. Trust supports operations.

## Trust Spine

The Trust Spine is the evidence-to-operations path for UAR:

```text
Replay
  -> T1: Replay Confidence
  -> T2: Runtime Health
  -> T3: Burn-In Evidence
  -> T4: Certification Engine
  -> T5: Mission Control
  -> T6: Replay Explorer
```

### Priority Order

1. Replay Confidence (#74)
2. Runtime Health (#83)
3. Burn-In Framework (#62)
4. Certification Engine (#57, #70)
5. Mission Control (#72, #55)
6. Replay Explorer (#56)

## Phase T1 — Replay Confidence

Primary issue: #74  
Related issue: #58

Purpose: define and implement the first measurable trust primitive.

Inputs:

- Event completeness
- Timeline completeness
- Artifact completeness
- Store consistency
- Replay reconstruction success

Outputs:

- Confidence score, 0-100
- Confidence tier
- Warning set
- Evidence report

## Phase T2 — Runtime Health

Primary issue: #83

Purpose: report what is currently running. Provide a structured health view that operators can rely on.

Outputs:

- RuntimeHealthReport
- Health score, 0-100
- Health tier
- Component status map
- Active run count
- Error rate
- Operator-facing health summary

## Phase T3 — Burn-In Framework

Primary issue: #62

Purpose: generate runtime reliability evidence.

Burn-in classes:

- Smoke: starts, stops, streams, persists
- Soak: long-running stability
- Pressure: event volume, subscriber load, storage pressure

Outputs:

- Burn-in score
- Reliability metrics
- Failure evidence
- Certification inputs

## Phase T4 — Certification Engine

Primary issues: #57, #70

Purpose: define UAR Trust Model v1 and convert evidence into certification artifacts.

Inputs:

- Replay confidence
- Burn-in score
- Runtime health
- Contract compliance

Outputs:

- Certification level (Experimental / Silver / Gold)
- Evidence bundle
- Certification report
- Operator-facing trust status

## Phase T5 — Mission Control

Primary issue: #72  
Related issue: #55

Purpose: synthesize runtime state into one operator view.

Mission Control first-class signals:

- Runtime health
- Replay confidence
- Certification status
- Active runs
- Topology state
- Alerts
- Live event feed

## Phase T6 — Replay Explorer

Primary issue: #56

Purpose: allow operators to inspect what happened and why.

Core surfaces:

- Run browser
- Timeline explorer
- Event viewer
- Confidence overlay
- Run comparison

## Freeze Directive

Until Trust Spine milestones are complete, defer major expansion in:

- Runtime infrastructure
- Marketplace systems
- Agent economy systems
- Workflow studio systems
- Large governance expansions

Reason: Capability Atlas audits showed that infrastructure maturity exceeds trust maturity.

## v1.1 Exit Criteria

Trust:

- Replay Confidence operational
- Burn-In evidence generated
- Certification operational

Operator Experience:

- Mission Control operational
- Replay Explorer operational

Documentation:

- Capability Atlas frozen
- Runtime Guarantees documented
- Trust Spine documented

## Current Status

**Phase Transition: 2026-05-31**

UAR has formally transitioned from **Trust Spine Construction Phase**
into **Trust Spine Hardening Phase**.

| Phase | Status | Notes |
|-------|--------|-------|
| T1 Replay Confidence | Complete | #74 — all tests green |
| T2 Runtime Health | Implemented | #83 — hardening pending |
| T3 Burn-In Framework | Implemented | #62 — persistence pending |
| T4 Certification Engine | Implemented | #57/#70 — refactor pending |
| T5 Mission Control | Implemented | #72/#55 — query consolidation pending |
| T6 Replay Explorer | Implemented | #56 — presentation layer |

Infrastructure Expansion: Frozen — no new subsystems until
hardening milestones complete.

## Hardening Backlog

Open items following phase transition (see issue docs in
`docs/issues/`):

- **#85** Runtime Health Query Consolidation — collapse 4 store scans
  per Mission Control request into a single snapshot query
- **#86** Burn-In Persistence Layer — survive restart; write
  `BurnInReport` to the run store rather than an in-process module var
- **#87** Certification Engine Refactor — remove pressure-score and
  hardening-era remnants; inputs are T1/T2/T3 only

## Hardening Freeze Directive

No new Trust Spine phases.
No new concepts, layers, or subsystems.

Permitted work during Hardening Phase:

- Performance (query consolidation, caching)
- Persistence (burn-in store, report durability)
- Correctness (ownership, concurrency, error paths)
- Observability (structured logging, metrics)

Note: Former T2 (Runtime Guarantees, #69/#68) is absorbed into T4
Certification Engine inputs. The guarantee catalog becomes part of
the certification scoring contract, not a standalone trust phase.
