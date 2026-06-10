# D5B Operator Evidence Path

## Status

D5B defines the operator evidence path for UAR operational productization.

## Purpose

Convert UAR validation, replay, burn-in, certification, and trust data into one repeatable operator workflow.

## Canonical Flow

```text
Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement
```

## Step 1 — Signal

A signal is any operator-facing condition that deserves attention.

Examples:

- runtime warning
- replay confidence degradation
- burn-in failure
- certification downgrade
- entity integrity warning
- fleet pressure
- recurring incident
- recommendation drift

## Step 2 — Mission Control

Mission Control is the operator entry point.

It should answer:

- What is happening?
- Is it urgent?
- Which run or entity is affected?
- Is replay available?
- Is certification or burn-in degraded?
- What evidence should be opened next?

## Step 3 — Replay

Replay is the investigation spine.

It should preserve:

- run identity
- event timeline
- replay confidence
- failure path
- reconstruction state
- warnings and divergence

## Step 4 — Evidence Pack

The evidence pack turns investigation into an auditable artifact.

It should include:

- signal summary
- Mission Control snapshot
- replay summary
- burn-in status
- certification status
- trust summary
- linked incidents
- operator notes
- outcome reference

## Step 5 — Outcome

The operator records what happened.

Outcome types:

- resolved
- recurred
- ignored
- deferred
- escalated
- false positive

Outcome capture should preserve:

- actor
- timestamp
- run ID
- signal ID
- evidence reference
- recommendation reference, if present

## Step 6 — Trust Movement

Trust movement closes the loop.

The system should be able to answer:

- Did the recommendation help?
- Did the issue recur?
- Did confidence improve or degrade?
- Is there enough replay evidence to trust this recommendation type?

## Operator Rule

No operational signal is complete until it has either:

1. a replay/evidence path, or
2. an explicit documented reason why replay/evidence is unavailable.

## Acceptance Criteria

D5B is complete when:

- The evidence path is documented.
- Mission Control signals can be mapped to replay/evidence/outcome/trust.
- Evidence Pack v2 fields can be derived from this path.
- D5C can implement or document the Evidence Pack v2 shape.

## Guardrails

- Do not create a second Mission Control.
- Do not create a second replay surface.
- Do not weaken D4G warning gates.
- Reuse existing burn-in, certification, replay, trust, and Mission Control data.
