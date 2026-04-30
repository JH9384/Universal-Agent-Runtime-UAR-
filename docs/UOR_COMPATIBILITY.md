# UOR Compatibility Matrix

This document defines how UAR stays compatible with UOR-style object principles while making clear what is UOR-aligned, what is a UAR extension, and what still requires validation.

## Compatibility Goal

UAR should act as an execution layer over UOR-style objects without redefining UOR identity, object reference, or dataset semantics.

## Core Compatibility Principles

| Principle | UAR Status | Notes |
|---|---:|---|
| Content-addressed object identity | Aligned | Objects use deterministic SHA-256 digests over canonical JSON envelopes. |
| Object metadata / attributes | Aligned | Objects carry `attributes` for discovery and filtering. |
| Object links / references | Aligned | Objects carry `links` with `rel` and `target`. |
| Datasets as objects | Aligned | Composer creates collection/dataset-style objects. |
| Execution records as objects | UAR extension | Execution produces output objects and execution-record objects. |
| Runtime code as objects | UAR extension | Runtime snippets are registered as objects and executed by name/digest. |
| Agent classes | UAR extension | UOR does not require this layer; UAR adds agents for execution/control. |
| Workflow chaining | UAR extension | Linear workflows operate over object outputs. |
| URI scheme | Internal convention only | Do not claim `uor://` as canonical unless validated against a UOR spec. |
| Schema extensions | Partial | Schema names exist in envelopes, but formal schema validation is not yet implemented. |

## UAR Object Envelope

```json
{
  "digest": "sha256:<hash>",
  "mediaType": "application/json",
  "mode": "immutable",
  "schema": "uor.schema.object.v1",
  "attributes": {},
  "links": [],
  "content": {}
}
```

## Compatibility Rules

1. UAR must not redefine object identity.
2. UAR must treat digests as primary identity anchors.
3. UAR extensions must be represented as objects, links, or attributes.
4. Runtime execution must produce traceable output objects.
5. UAR must clearly label extensions as UAR-specific.

## Current Gaps

- Formal UOR schema validation is not implemented.
- Object modes are represented but not deeply enforced.
- Link relation vocabulary is not standardized yet.
- External UOR interoperability tests do not exist yet.
- Public UOR reference test fixtures are not included yet.

## Compatibility Verdict

Current UAR is **UOR-aligned**, not yet proven **fully UOR-conformant**.

Use this wording until external compatibility tests exist.
