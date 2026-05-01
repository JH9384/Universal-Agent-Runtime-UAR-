# UAR UX Refinement Spec

## Purpose

This document refines the UAR canvas experience from functional UI into a polished, usable product experience.

The UX goal:

```text
make verifiable computation feel obvious
```

---

## UX North Star

A new user should understand this within five seconds:

```text
Objects go in. Runtimes act. Results appear. Proof follows.
```

The UI should feel like:

- Google-level clarity
- Figma-like spatial manipulation
- Notion-like progressive disclosure
- developer-tool precision

---

## Canvas Interaction Rules

### Pan and Zoom

Required behavior:

- Mouse wheel / trackpad: zoom
- Space + drag: pan
- Two-finger trackpad: pan
- Fit-to-view button
- Reset view button

Rules:

- Zoom should center on cursor
- Canvas should never jump unexpectedly
- Current zoom level should be recoverable

---

### Node Dragging

Required behavior:

- Drag node to move
- Hold shift to multi-select
- Drag selection group to move multiple nodes
- Selected nodes show clear blue outline
- Dragging should feel smooth and immediate

Rules:

- Node position updates optimistically
- Backend is not called during drag
- Persist layout separately from object identity

---

### Selection Model

Selection states:

```text
none → one node → many nodes
```

Behavior:

- Click node: select only that node
- Shift-click node: toggle selection
- Click background: clear selection
- Double-click node: inspect
- Right-click node: context menu

---

## Floating Runtime Bar

Appears when one or more nodes are selected.

Default layout:

```text
[ Runtime ▼ ] [ Run ] [ Replay ] [ Proof ] [ More ⋯ ]
```

Rules:

- Position near selected node/group center
- Avoid covering selected nodes
- Reposition if near viewport edge
- Disable Run if runtime/input compatibility is invalid
- Show tooltip explaining disabled state

---

## Node Visual Design

### Base Node Anatomy

```text
┌────────────────────────┐
│ icon  label            │
│ type  sha256:abcd…     │
│ badges                 │
└────────────────────────┘
```

Node information hierarchy:

1. Human label
2. Type
3. Status badges
4. Short digest

Never lead with raw digest.

---

### Node Types

| Type | Icon | Treatment |
|---|---|---|
| Object | □ | neutral card |
| Markdown | 📄 | document card |
| Runtime | ⚙ | action card |
| Result | ◆ | emphasized card |
| Proof | 🔐 | trust card |
| Workflow | ⛓ | grouped card |

---

### Status Badges

| Badge | Meaning |
|---|---|
| hash ✓ | integrity verified |
| replay ✓ | deterministic replay passed |
| proof ✓ | proof attached |
| UOR ✓ | external UOR evidence attached |
| warn | schema or runtime warning |
| error | failed execution or invalid object |

Badges should be small and calm, not noisy.

---

## Inspector UX

The inspector should be layered.

### Default View

Show:

- label
- type
- short digest
- content preview
- primary status badges

### Advanced View

Expandable sections:

- full attributes
- links
- lineage timeline
- replay result
- integrity audit
- proof object
- raw JSON

Rules:

- Raw JSON is always behind a toggle
- Proof data is summarized before raw display
- Errors include remediation text

---

## Lineage Visualization

Lineage should appear in two forms:

### Timeline

Inspector view:

```text
created → used by runtime → output created → proof attached
```

### Canvas Overlay

Optional overlay:

- highlight ancestor nodes
- highlight descendant nodes
- dim unrelated nodes

---

## Verification UX

Verification should be visible but not overwhelming.

### Integrity

When object audit passes:

```text
hash ✓ Digest verified
```

When fails:

```text
hash ! Digest mismatch — object may be modified
```

### Replay

When deterministic:

```text
replay ✓ Same result on repeated execution
```

When mismatch:

```text
replay ! Result changed on replay
```

### Proof

When attached:

```text
proof ✓ Signed proof object attached
```

When UOR evidence exists:

```text
UOR ✓ Bridge evidence attached
```

---

## Empty States

### Empty Canvas

Message:

```text
Drop a file, create an object, or choose a runtime to begin.
```

Primary actions:

- Create Object
- Drop Markdown
- View Demo

---

### No Selection

Inspector message:

```text
Select a node to inspect its content, lineage, and verification state.
```

---

### No Runtimes

Runtime bar message:

```text
No runtimes available. Seed or register a runtime first.
```

---

## Error UX

Errors should be actionable.

Bad:

```text
Execution failed
```

Good:

```text
Execution failed: selected object type is incompatible with runtime.
Try selecting a numeric object or choose a text runtime.
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Cmd/Ctrl + K | Open command palette |
| Delete/Backspace | Remove selected node from canvas layout |
| Cmd/Ctrl + Enter | Run selected runtime |
| Space + Drag | Pan canvas |
| Cmd/Ctrl + 0 | Fit to view |
| Esc | Clear selection / close modal |
| Shift + Click | Multi-select |

Note: deleting a canvas node must not delete the underlying object unless explicitly confirmed.

---

## Command Palette

Command palette should support:

- create object
- import file
- run runtime
- replay execution
- audit object
- attach proof
- toggle overlays
- search object by digest or label

---

## Mobile / Web Responsiveness

Desktop is primary, but web/mobile must remain usable.

### Tablet

- collapsible sidebar
- inspector as drawer
- canvas remains primary

### Mobile

- object list → canvas → inspector as stacked modes
- no dense multi-panel layout
- bottom action sheet replaces floating runtime bar

Mobile modes:

```text
Objects | Canvas | Inspect
```

---

## Accessibility

Minimum requirements:

- keyboard navigation for nodes
- visible focus states
- color is not the only status indicator
- status badges include text labels
- inspector sections use semantic headings

---

## Animation / Motion

Use motion sparingly.

Good uses:

- node appears after execution
- edge draws in after result creation
- badge updates after verification
- inspector slides open

Avoid:

- decorative animations
- constant motion
- distracting particle effects

Motion principle:

```text
animate causality, not decoration
```

---

## Runtime Compatibility UX

Future runtime records should declare:

```text
input_types
output_type
execution_mode
```

The UI should use this to:

- suggest compatible runtimes
- disable incompatible runtimes
- warn before execution

---

## Demo Flow

The default demo should prove the product in under 60 seconds.

1. Drop `README.md`
2. Markdown node appears
3. Select node
4. Floating bar appears
5. Choose `markdown_summarize`
6. Result node appears
7. Click result
8. Inspector shows lineage and proof/audit status

---

## UX Acceptance Criteria

The MVP UX is acceptable when a first-time user can:

- create or import an object
- see it on canvas
- run a runtime
- identify the result
- inspect lineage
- understand whether the result is verified

without reading developer documentation.

---

## Final UX Principle

The interface should make trust visible.

UAR is not only about doing computation. It is about showing:

```text
what happened, why it happened, and whether it can be trusted
```
