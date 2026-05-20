# UOR Compatibility Matrix

This document defines how UAR stays compatible with UOR-style object principles while making clear what is UOR-aligned, what is a UAR extension, and what still requires validation.

## Compatibility Goal

UAR should act as an execution layer over UOR-style objects without redefining UOR identity, object reference, or dataset semantics.

## UOR-ADDR-1 Implementation

UAR implements UOR-ADDR-1 bounded shape recursion based on the Rust reference specification (UOR-Foundation/uor-addr). Note: No official Python `uor-addr` package exists on PyPI; this is a native Python implementation aligned with the UOR Foundation's Rust specification.

### Typed JSON Value Handling (CT-T)
- Case distinction for all JSON types: null, false, true, number, string, array, object
- Semantically distinct values (e.g., 42 vs "42") produce distinct canonical forms
- Case tags embedded in canonical serialization for structural distinction

### Bounded Recursion (CT-B)
- Maximum recursion depth: 1000 levels (prevents stack overflow)
- Maximum array length: 10,000 elements
- Maximum object key count: 10,000 keys
- Recursion bounds enforced during both parsing and canonicalization

### JCS-RFC8785 Canonicalization
- Uses standard RFC 8785 JSON Canonicalization Scheme (JCS) via `rfc8785` Python package
- Replaces custom canonicalization with compliant JCS implementation
- Ensures interoperability with UOR Foundation reference implementation
- Idempotent: canonical input remains canonical

### Unicode NFC Normalization
- Applies Unicode NFC normalization to all strings using Python's built-in `unicodedata` module
- Ensures consistent representation across Unicode equivalent forms
- Compliant with UOR-ADDR-1 specification requirements

### In-Surface Canonicalization
- Public `canonicalize()` function replaces legacy `jcs_nfc` approach
- Case tag bytes included in canonical form
- SHA-256 sensitivity bound ensures distinct inputs yield distinct digests

### Content-Derived Addressing
- SHA-256 digests computed over canonical bytes
- Format: `sha256:<hex-digest>`
- Deterministic: same content always produces same digest
- Used for object identity in UOR-aligned envelopes

## UOR Foundation Repository Alignment

UAR aligns with the following UOR Foundation repositories:

### UOR-Foundation/UOR-Framework
- **Status**: Reference specification (Rust workspace)
- **UAR Alignment**: UAR is an execution layer, not a framework reimplementation
- **Scope**: UAR ingests and emits UOR-style objects without redefining UOR identity

### UOR-Foundation/uor-addr
- **Status**: Reference Rust implementation of UOR-ADDR-1
- **UAR Alignment**: Native Python implementation of UOR-ADDR-1 specification
- **Compliance**: Implements core UOR-ADDR-1 features (CT-T, CT-B, JCS-RFC8785, Unicode NFC)

### UOR-Foundation/prism
- **Status**: Standard library implementation (Rust)
- **UAR Alignment**: UAR does not implement PRISM; uses Python ecosystem instead
- **Scope**: PRISM is a Rust standard library; UAR uses Python equivalents where needed

### UOR-Foundation/atlas-embeddings
- **Status**: Archived mathematical research (Lie groups)
- **UAR Alignment**: Not applicable to UAR's execution layer scope
- **Scope**: Mathematical research beyond UAR's requirements

### UOR-Foundation/ego-guard-forge
- **Status**: Repository not found (may be moved or archived)
- **UAR Alignment**: Not applicable to UAR's execution layer scope

### UOR-Foundation/UOR-H1-HPO-Candidate
- **Status**: Repository not found (may be moved or archived)
- **UAR Alignment**: Not applicable to UAR's execution layer scope

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

## Ecosystem Integrations

UAR provides first-class integration modules for the broader UOR ecosystem:

| Project | Module | Status | Notes |
|---|---|---|---|
| UOR-Foundation/uor-addr | `uar.core.uor_ecosystem.UORAddrClient` | Active | UOR-ADDR-1 canonicalization, digest computation, cache resolution |
| gethologram.ai | `uar.core.uor_ecosystem.HologramClient` | Active | Geometric inference API with graceful mock fallback |
| moltbook.com/m/uor | `uar.core.uor_ecosystem.MoltbookClient` | Active | Forum read/search; write gated by API key |
| afflom/prism-btc | `uar.core.uor_ecosystem.PrismBTCClient` | Placeholder | BTC anchoring pending public release |
| dkypuros/Project_Severance_AI | `uar.core.uor_ecosystem.SeveranceAIClient` | Placeholder | Inference pending public release |
| AdamPippert/Anunix | `uar.core.uor_ecosystem.AnunixClient` | Placeholder | Host automation pending public release |
| dkypuros/atomic-lang-model | `uar.skills.atomic_lang_model` | Active | ALM analyze/generate/verify skills |
| UOR-Foundation/atlas-embeddings | `uar.core.atlas_embeddings` | Active | Golden Seed Vector / E8 integration |
| UOR-Foundation/prism | `uar.core.prism_integration` | Active | Data refraction / facet model |
| UOR-Foundation/ego-guard-forge | `uar.core.ego_guard_forge` | Active | Security policy enforcement |

Each integration is exposed as both a Python client class and a registered UAR skill, so they can be composed into recipes and execution pipelines.

## Current Gaps

- Formal UOR schema validation is not implemented.
- Object modes are represented but not deeply enforced.
- Link relation vocabulary is not standardized yet.
- External UOR interoperability tests do not exist yet.
- Public UOR reference test fixtures are not included yet.
- prism-btc, Severance AI, and Anunix integrations are placeholder stubs awaiting public API availability.

## Compatibility Verdict

Current UAR is **UOR-aligned**, not yet proven **fully UOR-conformant**.

Use this wording until external compatibility tests exist.
