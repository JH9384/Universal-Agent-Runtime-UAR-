# Observer Safety Rules

Mission Control exists to observe runtime state without destabilizing runtime state.

## Operational Principle

The observer layer is part of the runtime topology.

It must therefore obey:
- bounded propagation
- replay continuity
- pressure awareness
- graceful degradation

## Forbidden Behaviors

Operational tooling must never:
- amplify websocket storms
- create render cascades
- bypass runtime throttling
- starve runtime queues
- violate replay synchronization

## Required Behaviors

Operational tooling should:
- batch updates safely
- throttle deterministically
- compact timelines under pressure
- degrade visual fidelity before causality
- preserve replay continuity first

## Timeline Rules

Timeline systems should:
- virtualize long histories
- compact low-priority events
- preserve critical replay markers
- maintain deterministic ordering

## Topology Rules

Topology visualizers should:
- cap render density
- batch graph updates
- suppress animation under pressure
- prioritize partition visibility

## Replay Rules

Replay panels should:
- preserve synchronization state
- surface divergence clearly
- avoid speculative reconstruction
- prefer continuity over visual density
