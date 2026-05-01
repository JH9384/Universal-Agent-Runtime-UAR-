# UAR UI System Spec

## Purpose

This document defines the UI system for the Universal Agent Runtime (UAR): a visual, canvas-based environment for working with UOR-style objects, runtimes, lineage, proofs, and verification signals.

The UI goal is simple:

```text
make object computation visible, controllable, and verifiable
```

---

## Product Frame

UAR is not a generic dashboard. It is a visual computation environment.

Users should be able to:

1. Load or create objects.
2. Place objects on a canvas.
3. Select a runtime/model.
4. Execute computation.
5. See result objects appear.
6. Inspect lineage, integrity, determinism, and proofs.

Core loop:

```text
ingest → object → canvas node → runtime → result object → lineage/proof
```

---

## Primary Layout

The UI uses a four-region layout.

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Runtime / Command Bar                                    │
├───────────────┬───────────────────────────────┬──────────────┤
│ Object Sidebar│ Canvas Workspace              │ Inspector    │
│               │                               │ Panel        │
└───────────────┴───────────────────────────────┴──────────────┘
```

### 1. Top Runtime / Command Bar

Purpose:

- choose runtime
- run selected objects
- replay execution
- toggle overlays
- show system status

Expected controls:

- Runtime selector
- Run button
- Replay button
- Determinism toggle
- Proof overlay toggle
- Integrity overlay toggle
- Backend health indicator

---

### 2. Left Object Sidebar

Purpose:

- show object inventory
- ingest files/Markdown
- search/filter objects
- drag objects onto canvas

Object list item should show:

- label
- object type
- short digest
- status badges

Example:

```text
📄 README.md       markdown   sha256:ab12…
🔢 42              number     sha256:f9a1…
⚙ sum_contents    runtime    sha256:77c3…
```

---

### 3. Center Canvas Workspace

Purpose:

- visual object graph
- draggable nodes
- edges showing relationships
- floating execution controls

Canvas node types:

| Node Type | Meaning |
|---|---|
| Object Node | Base UOR-style object |
| Runtime Node | Runtime/model/operator |
| Result Node | Output from execution |
| Proof Node | Formal proof artifact |
| Workflow Node | Multi-step pipeline |

Node should display:

- icon/type
- label
- short digest
- status badges

Edges should represent:

- `used`
- `runtime`
- `output`
- `contains`
- `proof-of`
- `lineage`

---

### 4. Right Inspector Panel

Purpose:

- inspect selected node deeply
- expose verification and proof data
- show raw object only when requested

Sections:

1. Summary
2. Content Preview
3. Attributes
4. Links
5. Lineage
6. Integrity Audit
7. Replay / Determinism
8. UOR Proofs
9. Raw JSON toggle

---

## Interaction Model

### Select Object

```text
click node → selected node → inspector updates
```

### Multi-select

```text
shift-click nodes → selected set → floating runtime action appears
```

### Execute Runtime

```text
selected objects + runtime → POST /agents/execution/run → result node appears
```

### Replay Runtime

```text
selected execution → POST /agents/execution/replay → determinism badge updates
```

### Inspect Lineage

```text
select node → GET /agents/lineage/trace → lineage timeline appears
```

### Verify Integrity

```text
select node → GET /audit/object → hash badge updates
```

### Attach Proof

```text
select node → GET /uor/proof/attach → proof node + proof badge appears
```

---

## Floating Runtime Execution

When one or more nodes are selected, a compact floating action bar appears near the selection.

```text
[ runtime ▼ ] [ Run ] [ Replay ] [ Proof ]
```

Rules:

- appears only with selection
- follows selection center
- does not obscure selected node
- disabled when backend is unhealthy
- runtime selector uses `/runtimes`

---

## Visual Status Badges

Every node can display small badges.

| Badge | Meaning |
|---|---|
| ✔ hash | object digest verified |
| ↻ replay | deterministic replay passed |
| ! replay | replay mismatch |
| 🔐 proof | formal proof attached |
| 🌐 UOR | UOR bridge evidence attached |
| ⚠ | warning or schema issue |

---

## Backend Endpoint Mapping

| UI Action | Endpoint |
|---|---|
| Create object | `POST /objects` |
| Read object | `GET /objects?digest=...` |
| List runtimes | `GET /runtimes` |
| Register runtime | `POST /runtimes/register` |
| Execute runtime | `POST /agents/execution/run` |
| Replay execution | `POST /agents/execution/replay` |
| Trace lineage | `GET /agents/lineage/trace?digest=...` |
| Audit object | `GET /audit/object?digest=...` |
| Audit all | `GET /audit/all` |
| UOR conformance | `GET /uor/conformance` |
| Attach UOR proof | `GET /uor/proof/attach?digest=...` |

Some endpoints are planned and should be hidden until implemented.

---

## React Component Architecture

Recommended component tree:

```text
App
├── AppShell
│   ├── TopCommandBar
│   ├── ObjectSidebar
│   │   ├── ObjectSearch
│   │   ├── FileDropZone
│   │   └── ObjectList
│   ├── CanvasWorkspace
│   │   ├── CanvasNode
│   │   ├── CanvasEdge
│   │   └── FloatingRuntimeBar
│   └── InspectorPanel
│       ├── SummarySection
│       ├── ContentPreview
│       ├── AttributesSection
│       ├── LineageTimeline
│       ├── IntegrityPanel
│       ├── ReplayPanel
│       ├── ProofPanel
│       └── RawJsonPanel
```

---

## Frontend State Model

```ts
type CanvasState = {
  objects: UarObject[];
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  selectedNodeIds: string[];
  activeRuntime: string | null;
  activeInspectorObject: string | null;
  overlays: {
    lineage: boolean;
    integrity: boolean;
    proofs: boolean;
    determinism: boolean;
  };
  backendStatus: 'unknown' | 'healthy' | 'error';
};
```

---

## Node Model

```ts
type CanvasNode = {
  id: string;
  objectDigest: string;
  kind: 'object' | 'runtime' | 'result' | 'proof' | 'workflow';
  label: string;
  x: number;
  y: number;
  badges: NodeBadge[];
};
```

---

## Edge Model

```ts
type CanvasEdge = {
  id: string;
  from: string;
  to: string;
  relation: 'used' | 'runtime' | 'output' | 'contains' | 'proof-of' | 'lineage';
};
```

---

## Visual Design Direction

Style target:

- Google clean
- Figma-like direct manipulation
- white background
- soft grid
- minimal shadows
- status by badges, not clutter
- advanced controls hidden until needed

Do not make the UI mystical or decorative. The system can support symbolic modes later, but the default production UX should be clear, calm, and technical.

---

## UX Principles

1. **No hidden computation** — every execution produces visible output.
2. **No dead surfaces** — every major visual element should inspect or act.
3. **Progressive disclosure** — show simple path first, advanced proof/runtime details on demand.
4. **Trust is visible** — integrity, replay, lineage, and proof signals must be exposed.
5. **Objects are first-class** — files, Markdown, numbers, runtimes, proofs, and model outputs are all objects.

---

## MVP Completion Checklist

### Must Have

- [ ] Object sidebar
- [ ] Drag/drop file and Markdown ingestion
- [ ] Canvas nodes and edges
- [ ] Runtime selector
- [ ] Floating runtime action bar
- [ ] Result node creation
- [ ] Inspector summary
- [ ] Lineage timeline

### Should Have

- [ ] Integrity badge
- [ ] Replay badge
- [ ] Proof badge
- [ ] UOR conformance status
- [ ] Raw JSON toggle

### Later

- [ ] Workflow editor
- [ ] Proof graph visualization
- [ ] Multi-runtime pipelines
- [ ] Local/OpenAI model chooser
- [ ] Symbolic mode overlay

---

## Current Canva Direction

The selected Canva mockup direction should be treated as visual reference only, not source of truth. The source of truth is this UI spec plus the backend contracts.

Reference intent:

```text
minimal canvas workspace + object sidebar + inspector + runtime bar
```

---

## Final UI Thesis

UAR should make this visible:

```text
objects enter → computation acts → results appear → proof follows
```

The best UI is the one that lets a user understand that loop in under five seconds.
