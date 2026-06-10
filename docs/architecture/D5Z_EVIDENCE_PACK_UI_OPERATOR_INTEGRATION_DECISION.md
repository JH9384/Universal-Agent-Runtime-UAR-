# D5Z Evidence Pack UI / Operator Integration Decision

## Status

D5Z decides the operator-facing UI integration path for Evidence Pack v2 after D5Y authority mapping.

## Context

Evidence Pack v2 now has:

- read-only core builder,
- local CLI generation,
- live capture script,
- Make smoke target,
- authenticated API endpoint,
- active API contract tests,
- live API smoke,
- CI-visible Evidence Pack gates,
- authority map.

## UI Integration Goal

Operators should be able to move from an observed run, warning, recommendation, or Mission Control state into a structured Evidence Pack without guessing which command or endpoint to use.

## Candidate UI Patterns

### Option A — Mission Control Evidence Pack Button

Add an `Evidence Pack` action button near run/recommendation/incident surfaces.

Behavior:

```text
Click Evidence Pack -> fetch /api/uar/evidence-pack/{run_id}?include_markdown=true
```

Pros:

- direct operator workflow,
- discoverable,
- aligns with Mission Control as command center.

Cons:

- requires UI state to know selected `run_id`,
- needs markdown rendering or copy/download behavior.

### Option B — Replay Explorer Evidence Pack Link

Add Evidence Pack access inside Replay Explorer for a selected run.

Behavior:

```text
Replay Explorer -> Evidence Pack section/action
```

Pros:

- strongest run identity context,
- evidence pack naturally follows replay analysis,
- lower ambiguity than global Mission Control.

Cons:

- less visible from top-level Mission Control,
- requires operator to enter Replay Explorer first.

### Option C — Evidence Pack Panel

Create a standalone panel that accepts a `run_id` and renders pack availability + markdown.

Pros:

- clean product surface,
- easy to test independently,
- can later support export/copy.

Cons:

- adds a new UI surface,
- risks sprawl if not linked tightly to Mission Control/Replay.

## Decision

Proceed with Option B first: Replay Explorer Evidence Pack Link.

## Reason

Evidence Pack v2 is run-centered. Replay Explorer already owns run context and failure-path context, so it is the safest first UI integration point. Mission Control can link to Replay Explorer, and Replay Explorer can expose the Evidence Pack action once a run is selected.

## First UI Behavior

1. Add an Evidence Pack action to Replay Explorer.
2. Fetch:

```text
GET /api/uar/evidence-pack/{run_id}?include_markdown=true
```

3. Render section availability first.
4. Render markdown second.
5. Include copy/download affordance later, not in first pass.

## Non-Goals

D5Z does not implement UI code.

Do not add:

- artifact promotion from UI,
- outcome creation from Evidence Pack view,
- trust mutation from Evidence Pack view,
- a second Evidence Pack format,
- unauthenticated Evidence Pack access.

## Required Next Lane

D6A should implement the Replay Explorer Evidence Pack action behind the existing authenticated API.

## Guardrails

- Evidence Pack UI remains read-only.
- UI must not write reports or promote artifacts.
- UI must not mutate outcomes, trust, runs, replay, burn-in, or certification.
- Missing evidence must remain visible and explicit.
- Mission Control should route to Replay Explorer rather than duplicating Evidence Pack behavior initially.
