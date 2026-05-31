# Runtime Boundary Audit

## Goal

Preserve UAR as a universal execution runtime.

The runtime should survive removal of all skills, agents, recipes, and external integrations.

---

## Runtime Core

Must remain in core:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Executor Kernel
- Scheduler Interfaces
- Replay Validation

If removed, execution truth is compromised.

---

## Runtime Services

Belong in services:

- Metrics
- Cache
- Persistence
- Audit
- UOR Addressing
- Witness Generation

These support execution but are not execution itself.

---

## Workloads

Belong outside runtime:

- Skills
- Recipes
- Agents
- Scientific Compute Tasks
- Connectors
- Future Xarvus Modules

These are consumers of runtime capability.

---

## Operations

Belong outside runtime:

- Mission Control
- Runtime Health
- Replay Explorer
- Certification
- Topology Visualization

These observe runtime behavior.

They must never become execution dependencies.

---

## Runtime Purity Rule

For every new subsystem ask:

Can UAR still execute valid workloads if this subsystem is removed?

If YES:

It is not runtime core.

If NO:

It belongs in runtime core.

---

## Desired Long-Term Structure

uar-core/

- contracts
- executor
- scheduler
- events
- replay

uar-services/

- metrics
- persistence
- cache
- audit

uar-workloads/

- skills
- recipes
- agents
- integrations

uar-ops/

- mission-control
- replay-explorer
- health
- certification
- topology
