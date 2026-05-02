# Universal Agent Runtime (UAR)

UAR is an agnostic agent runtime and graph-based execution canvas.

It ingests inputs, normalizes them into internal runtime objects, composes those objects into graphs, executes agent functions over selected inputs, and exposes trace / verification surfaces for inspection.

## Architecture Positioning

This system is the **Universal Agent Runtime (UAR)**.

It is:

- an agnostic runtime
- an agent execution environment
- a graph-based computation system
- a document ingestion and transformation engine
- a runtime registry and execution surface

## UOR Relationship

UAR is **not** a Universal Object Runtime (UOR).

Instead, UAR is:

- **UOR-aligned** in selected object modeling principles
- capable of **UOR-compatible import/export** where useful
- designed to interoperate with UOR-style object systems through an optional bridge

UOR is treated as:

- a reference model
- a compatibility target
- an interoperability layer
- **not** the identity of this system

## Core Loop

```text
input/document → normalized objects → graph → agent runtime → result → trace/verify
```

## Terminology

- **UAR** — Universal Agent Runtime; this system.
- **Agent Runtime** — the execution layer that runs registered functions over selected objects.
- **Runtime** — an executable function such as `sum_contents`, `count_inputs`, or future model-backed functions.
- **Object** — an internal normalized data unit used by UAR.
- **Node** — the UI representation of an internal object, runtime marker, or parsed document section.
- **Graph** — a composed execution structure of nodes and edges.
- **Trace** — lineage and execution history for persisted objects.
- **Verification** — integrity checks over persisted objects; replay and proof are future layers.
- **UOR** — an external/reference object-runtime model; optional compatibility target only.

## Current Capabilities

- FastAPI backend
- Runtime registry
- Sandboxed expression execution
- Object creation and persistence
- Lineage tracing
- Integrity verification endpoint
- React canvas UI
- Node dragging and graph edges
- Markdown / text ingestion
- Markdown-to-graph parsing
- Section-aware Markdown chunking
- Local development boot script

## Non-Goals

UAR does not currently claim to be:

- a full UOR implementation
- a proof-carrying execution system
- a deterministic replay engine
- a production-secured multi-user runtime

Those may become compatibility or platform layers, but they are not the system identity.
