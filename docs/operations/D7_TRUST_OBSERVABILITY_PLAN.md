# D7 Trust Observability Plan

## Status

D7 is open.

D6 closed with the `v1.3.0` operator-loop baseline. D7 extends the system from operator action capture into trust observability without changing trust-learning behavior.

## Primary goal

Expose how operator outcomes, evidence links, recommendation effectiveness, calibration, and trust movement relate over time.

D7 is observability-first.

## Non-goals

- No new trust algorithm.
- No new outcome table.
- No hidden score mutation.
- No automatic trust promotion.
- No replacement for the existing recommendation outcome path.
- No new operator workflow fork.

## Starting invariant

D7 must reuse:

- existing recommendation outcome capture
- existing evidence pack linkage
- existing trust summary fields
- existing effectiveness and calibration concepts
- existing Mission Control patterns

## Operator questions D7 should answer

1. What changed trust?
2. Which recommendation was affected?
3. Which run/evidence supported the outcome?
4. Was the outcome resolved, recurred, or unknown?
5. Did trust movement align with later recurrence?
6. Are operators repeatedly acting on low-trust signals?
7. Are high-trust recommendations actually resolving issues?

## Planned slices

### D7A — Trust Observability Opening Pack

Document scope, invariants, and release boundary.

### D7B — Trust Movement Read Model

Create or expose a read-only trust movement summary using existing outcome and trust data.

### D7C — Mission Control Trust Timeline

Add a Mission Control panel or section showing recent trust movement events.

### D7D — Evidence Pack Trust Context

Show trust context inside Evidence Pack preview without changing Evidence Pack authority.

### D7E — Regression Coverage

Prove that trust observability is read-only and that outcome capture still posts through the existing recommendation outcome endpoint.

### D7F — Certification

Certify D7 as observability-only.

## Success condition

An operator can see why trust moved, what evidence supported the movement, and whether the movement came from existing outcome capture.

## Release target

D7 should eventually cut a minor observability tag after certification, but not before read-only behavior is proven.
