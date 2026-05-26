# UOR Public Surface Snapshot

This file captures the public UOR facts UAR must align with.

## Public entry points

- Foundation site: https://uor.foundation/
- Framework docs: https://www.uor.foundation/docs/uor-framework
- OpenAPI spec: https://uor.foundation/openapi.json
- Live API base: https://api.uor.foundation/v1
- Source/ontology: https://github.com/UOR-Foundation/UOR-Framework
- Crate: https://crates.io/crates/uor-foundation
- Docs: https://docs.rs/uor-foundation

## Core public claims

UOR describes a universal data infrastructure where objects are identified by what they are, not where they live. Public documentation emphasizes:

- content-derived addresses
- cryptographic/hash identity
- object attributes such as size, media type, and digest
- composability
- verification/proofs
- semantic interoperability

## OpenAPI structure

The public OpenAPI describes three spaces:

| Space | Namespaces | API group |
|---|---|---|
| Kernel | `u:`, `schema:`, `op:` | `/kernel` |
| Bridge | `resolver:`, `partition:`, `observable:`, `proof:`, `derivation:`, `trace:`, `cert:` | `/bridge` |
| User | `type:`, `morphism:`, `state:` | `/user` |

The documented end-to-end resolution cycle is:

```text
Context → Type → Resolver → Partition → Observable → Cert → Trace → Transform
```

## Critical identity

The public quick verification identity is:

```text
neg(bnot(42)) = neg(213) = 43 = succ(42)
```

For `n=8`, this is computed in `R_8 = Z/(2^8)Z`.

## UAR compatibility interpretation

UAR should not claim to be the UOR kernel. UAR is an execution layer that can ingest, represent, execute over, and emit UOR-style objects without breaking UOR identity assumptions.

## Compatibility language

Use:

> UAR is UOR-aligned and includes a compatibility validation path.

Do not yet use:

> UAR is fully UOR-conformant.

until external UOR fixtures and API interoperability tests pass.

## Alignment tracking

- Pinned upstream release: **UOR-Framework v0.5.2** (2026-05-23) with SHA-256
  digests recorded in `third_party/uor/DIGESTS.json`.
- `/api/health` exposes both the local UAR version and the pinned upstream tag
  (`uor_upstream_version`) so operators can monitor alignment in production.
- `scripts/fetch_uor_artifacts.py` + CI jobs fetch the ontology artifacts and
  (coming next) run SHACL/JSON Schema validation to detect drift early.
