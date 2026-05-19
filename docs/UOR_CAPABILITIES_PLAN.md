# UOR Capabilities Plan

## Overview

Based on UOR Foundation research and UAR's current UOR-aligned implementation, this document outlines opportunities to establish comprehensive UOR graphing, math, and related capabilities.

## Current UOR Implementation in UAR

### Implemented (UOR-Aligned)
- **UOR-ADDR-1**: Bounded JSON processing with case distinction (CT-T) and recursion bounds (CT-B)
- **Content-derived addressing**: SHA-256 digests over canonical JSON
- **Object envelopes**: digest, mediaType, mode, schema, attributes, links, content
- **Flexible GraphRAG**: GraphBackend, SearchStrategy, GraphEntity, GraphRelation

### UOR Foundation Components (Not Yet Integrated)
- **Ontology**: 34 namespaces, 474 classes, 948 properties
- **Foundation traits**: Rust-based trait definitions
- **Public artifacts**: JSON-LD, Turtle, OWL, JSON Schema, SHACL, EBNF
- **Conformance suite**: External interoperability tests

## Capability Opportunities

### 1. UOR Graphing Capability

#### Object Relationship Graphs
**Opportunity**: UOR object `links` form natural graphs where objects reference each other via `rel` and `target` attributes.

**Implementation**:
- Map UOR object envelopes to GraphEntity/GraphRelation in flexible_graphrag.py
- Object digest → entity_id
- Object attributes → entity properties
- Object links → graph relations (source: object digest, target: link target)
- Support Neo4j, Memgraph backends for persistent graph storage

**Use Cases**:
- Trace object provenance and derivation chains
- Visualize dataset relationships
- Query object correlations (hierarchical structures, decision trees)
- AI training data lineage

#### Dataset Traversal & Querying
**Opportunity**: UOR datasets are objects that can be queried by attributes (e.g., "find objects with webbed feet, feathers, bill").

**Implementation**:
- Implement attribute-based query language over object graphs
- Integrate with GraphRAG hybrid search (vector + property graph)
- Support SPARQL-like queries over UOR object collections

**Use Cases**:
- Semantic object discovery
- Dataset filtering by schema/attributes
- Pattern matching across object collections

### 2. UOR Math Capability

#### Critical Identity Operations
**Opportunity**: UOR defines a critical identity: `neg(bnot(42)) = succ(42)` in R_8 ring (Z/(2^8)Z).

**Implementation**:
- Add UOR identity module: `uar/uor/identity.py`
- Implement operations: neg, bnot, succ in modular arithmetic
- Support configurable ring size (default n=8)
- Add identity verification skill for object integrity checks

**Use Cases**:
- Object integrity verification
- Cryptographic operations on content addresses
- Mathematical proofs for object transformations

#### Content-Derived Addressing Math
**Opportunity**: SHA-256 digests provide cryptographic content addressing with mathematical properties.

**Implementation**:
- Extend compute_uor_digest with additional hash algorithms (SHA-3, BLAKE3)
- Implement hash-based set operations (union, intersection, difference) on object sets
- Add Merkle tree construction for object collections

**Use Cases**:
- Efficient object deduplication
- Delta encoding between object versions
- Cryptographic proof of object inclusion

#### Lie Groups & Mathematical Structures
**Opportunity**: UOR Foundation's atlas-embeddings repo explores Lie groups for mathematical foundations.

**Implementation**:
- Investigate integrating with sympy or numpy for Lie group operations
- Implement group theory operations on object transformations
- Add mathematical transformations as skills

**Use Cases**:
- Advanced cryptographic operations
- Geometric interpretations of object spaces
- Mathematical modeling of object relationships

### 3. Schema Validation

#### UOR Foundation Ontology Integration
**Opportunity**: UOR Foundation provides formal ontology (JSON Schema, SHACL, OWL).

**Implementation**:
- Download and integrate UOR Foundation ontology artifacts
- Add schema validation using uor.foundation.schema.json
- Implement SHACL validation for object constraints
- Support ontology-based type checking

**Use Cases**:
- Validate objects against UOR specification
- Ensure interoperability with UOR ecosystem
- Type-safe object construction

### 4. Object Modes Enforcement

#### Three UOR Object Modes
**Opportunity**: UOR defines Immutable Singular, Mutable Singular, Mutable Array modes.

**Implementation**:
- Add mode enforcement in object envelope validation
- Implement mode-specific behaviors:
  - Immutable: reject modifications, enforce digest integrity
  - Mutable Singular: allow content updates, track version history
  - Mutable Array: support dynamic element addition/removal
- Add mode transition rules

**Use Cases**:
- Enforce immutability for critical objects
- Support dynamic content for mutable objects
- Version control for object evolution

### 5. Link Resolution & Traversal

#### Standardized Link Relations
**Opportunity**: UOR uses links with `rel` and `target` for object references.

**Implementation**:
- Define standard link relation vocabulary (e.g., "contains", "references", "derives-from")
- Implement link resolution with fallback strategies (local cache → remote UOR API)
- Add link traversal depth limits to prevent infinite loops
- Support DNS-based location resolution

**Use Cases**:
- Cross-system object references
- Distributed object graphs
- Location-independent object access

### 6. Trace & Derivation Tracking

#### Execution Records as Objects
**Opportunity**: UAR can emit execution records as UOR objects for traceability.

**Implementation**:
- Define execution record schema (input, output, skill, timestamp, metadata)
- Emit execution records as UOR objects with digest-based identity
- Build derivation graphs showing object transformation chains
- Add trace query skills

**Use Cases**:
- Debugging and audit trails
- Reproducibility of agent workflows
- Performance analysis of skill execution

### 7. Conformance & Interoperability

#### External UOR Compatibility Tests
**Opportunity**: UOR Foundation provides conformance suite.

**Implementation**:
- Add UOR Foundation conformance tests to test suite
- Implement interoperability tests with UOR Foundation API
- Add fixture generation for reference test cases
- Enable conformance badge when tests pass

**Use Cases**:
- Validate UOR alignment claims
- Ensure interoperability with UOR ecosystem
- Continuous compliance monitoring

## Implementation Priority

### Phase 1: High Priority (Core Graphing & Math)
1. Object relationship graph mapping to GraphRAG
2. Critical identity operations (neg, bnot, succ)
3. Content-derived addressing enhancements (Merkle trees)
4. Dataset attribute-based querying

### Phase 2: Medium Priority (Schema & Modes)
5. UOR Foundation ontology integration
6. Object modes enforcement
7. Standardized link relations
8. Execution record objects

### Phase 3: Low Priority (Advanced)
9. Lie groups integration
10. External conformance tests
11. DNS-based location resolution
12. Advanced mathematical transformations

## Technical Considerations

### Dependencies
- **Graph databases**: Neo4j (already optional), Memgraph
- **Math libraries**: sympy, numpy for Lie groups
- **Schema validation**: jsonschema, pyshacl
- **Cryptography**: cryptography, hashlib

### Performance
- Graph traversal depth limits to prevent infinite loops
- Caching for frequently accessed objects
- Batch operations for bulk object processing
- Async I/O for remote object resolution

### Security
- Validate object digests before accepting
- Enforce mode-based access controls
- Rate limiting for remote UOR API calls
- Secure handling of cryptographic keys

## Success Metrics

- **Graphing**: Object graphs traversable, queryable, and visualizable
- **Math**: Critical identity operations verified, content addressing extended
- **Schema**: Objects validated against UOR Foundation ontology
- **Modes**: Object mode enforcement functional
- **Interoperability**: External UOR conformance tests passing

## References

- UOR Foundation: https://github.com/UOR-Foundation/UOR-Framework
- UOR Public Surface: https://uor.foundation/
- Red Hat UOR Article: https://next.redhat.com/2022/07/13/the-uor-framework/
- UOR Compatibility Matrix: docs/UOR_COMPATIBILITY.md
