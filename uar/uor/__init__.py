"""UOR compatibility layer for Universal Agent Runtime.

This module provides UOR-aligned functionality including:
- Bounded shape recursion for JSON processing
- Typed JSON value handling with case distinction
- Content-derived address computation
- Canonicalization with recursion bounds
- Critical identity operations (neg, bnot, succ in R_n ring)
- Graph integration for object relationship mapping
- Merkle tree construction for object collections
- Object modes enforcement (Immutable Singular, Mutable Singular,
  Mutable Array)
- Standardized link relation vocabulary
- Execution record emission as UOR objects
- Lie groups integration for mathematical foundations
- DNS-based location resolution for distributed graphs
- Advanced mathematical transformations
- SHACL validation for object constraints
- RDF and semantic web format support (JSON-LD, Turtle, OWL)
- Hash-based set operations on object collections
- Caching for frequently accessed objects
- Batch operations for bulk object processing
- Digest validation before accepting objects
- Mode-based access controls
- Rate limiting for remote UOR API calls
- Secure handling of cryptographic keys
"""

import logging

from .bounded_json import (
    JsonCase,
    JsonValue,
    canonicalize_json,
    compute_uor_digest,
    MAX_RECURSION_DEPTH,
    MAX_ARRAY_LENGTH,
    MAX_OBJECT_KEYS,
)

logger = logging.getLogger(__name__)

# Optional UOR capabilities - imported with error handling
try:
    from .identity import (
        bnot,
        neg,
        succ,
        verify_critical_identity,
        compute_identity_chain,
        UORIdentityVerifier,
    )
except ImportError:
    logger.exception("UOR identity module not available")
    bnot = neg = succ = None  # type: ignore
    verify_critical_identity = None  # type: ignore
    compute_identity_chain = None  # type: ignore
    UORIdentityVerifier = None  # type: ignore

try:
    from .graph_integration import (
        UOREnvelope,
        UORGraphMapper,
    )
except ImportError as e:
    msg = "UOR graph integration module not available: {e}".format(e=e)
    logger.warning(msg)
    UOREnvelope = None  # type: ignore
    UORGraphMapper = None  # type: ignore

try:
    from .merkle import (
        MerkleNode,
        MerkleProof,
        UORMerkleTree,
    )
except ImportError as e:
    msg = "UOR merkle module not available: {e}".format(e=e)
    logger.warning(msg)
    MerkleNode = None  # type: ignore
    MerkleProof = None  # type: ignore
    UORMerkleTree = None  # type: ignore

try:
    from .object_modes import (
        ObjectMode,
        ObjectVersion,
        UORObject,
        ObjectModeEnforcer,
    )
except ImportError as e:
    msg = "UOR object modes module not available: {e}".format(e=e)
    logger.warning(msg)
    ObjectMode = None  # type: ignore
    ObjectVersion = None  # type: ignore
    UORObject = None  # type: ignore
    ObjectModeEnforcer = None  # type: ignore

try:
    from .links import (
        LinkRelation,
        LinkRelationVocabulary,
    )
except ImportError as e:
    msg = "UOR links module not available: {e}".format(e=e)
    logger.warning(msg)
    LinkRelation = None  # type: ignore
    LinkRelationVocabulary = None  # type: ignore

try:
    from .execution_records import (
        ExecutionRecord,
        ExecutionRecordEmitter,
    )
except ImportError as e:
    msg = "UOR execution records module not available: {e}".format(e=e)
    logger.warning(msg)
    ExecutionRecord = None  # type: ignore
    ExecutionRecordEmitter = None  # type: ignore

try:
    from .schema_validation import (
        UORSchemaValidator,
    )
except ImportError as e:
    msg = "UOR schema validation module not available: {e}".format(e=e)
    logger.warning(msg)
    UORSchemaValidator = None  # type: ignore

try:
    from .lie_groups import (
        GroupOperation,
        GroupElement,
        LieGroupOperations,
        UORObjectTransformation,
    )
except ImportError as e:
    msg = "UOR lie groups module not available: {e}".format(e=e)
    logger.warning(msg)
    GroupOperation = None  # type: ignore
    GroupElement = None  # type: ignore
    LieGroupOperations = None  # type: ignore
    UORObjectTransformation = None  # type: ignore

try:
    from .dns_resolution import (
        RecordType,
        ObjectLocation,
        UORDNSResolver,
        DistributedObjectGraph,
        DNSBasedLinkResolver,
    )
except ImportError as e:
    msg = "UOR DNS resolution module not available: {e}".format(e=e)
    logger.warning(msg)
    RecordType = None  # type: ignore
    ObjectLocation = None  # type: ignore
    UORDNSResolver = None  # type: ignore
    DistributedObjectGraph = None  # type: ignore
    DNSBasedLinkResolver = None  # type: ignore

try:
    from .math_transformations import (
        TransformationType,
        Transformation,
        GroupTheoryOperations,
        UORObjectMathTransform,
    )
except ImportError as e:
    msg = "UOR math transformations module not available: {e}".format(e=e)
    logger.warning(msg)
    TransformationType = None  # type: ignore
    Transformation = None  # type: ignore
    GroupTheoryOperations = None  # type: ignore
    UORObjectMathTransform = None  # type: ignore

try:
    from .shacl_validation import (
        SHACLValidator,
        ConstraintViolation,
        SHACLValidationResult,
    )
except ImportError as e:
    msg = "UOR SHACL validation module not available: {e}".format(e=e)
    logger.warning(msg)
    SHACLValidator = None  # type: ignore
    ConstraintViolation = None  # type: ignore
    SHACLValidationResult = None  # type: ignore

try:
    from .rdf_formats import (
        RDFConverter,
        OWLConverter,
        RDFConversionResult,
    )
except ImportError as e:
    msg = "UOR RDF formats module not available: {e}".format(e=e)
    logger.warning(msg)
    RDFConverter = None  # type: ignore
    OWLConverter = None  # type: ignore
    RDFConversionResult = None  # type: ignore

try:
    from .hash_set_operations import (
        ObjectSet,
        HashSetOperations,
        ObjectSetComparison,
    )
except ImportError as e:
    msg = "UOR hash set operations module not available: {e}".format(e=e)
    logger.warning(msg)
    ObjectSet = None  # type: ignore
    HashSetOperations = None  # type: ignore
    ObjectSetComparison = None  # type: ignore

try:
    from .object_cache import (
        UORObjectCache,
        CacheEntry,
        CachedObjectAccessor,
    )
except ImportError as e:
    msg = "UOR object cache module not available: {e}".format(e=e)
    logger.warning(msg)
    UORObjectCache = None  # type: ignore
    CacheEntry = None  # type: ignore
    CachedObjectAccessor = None  # type: ignore

try:
    from .batch_operations import (
        BatchProcessor,
        BatchDeduplicator,
        BatchResult,
    )
except ImportError as e:
    msg = "UOR batch operations module not available: {e}".format(e=e)
    logger.warning(msg)
    BatchProcessor = None  # type: ignore
    BatchDeduplicator = None  # type: ignore
    BatchResult = None  # type: ignore

try:
    from .digest_validation import (
        DigestValidator,
        DigestVerifier,
        ValidationResult,
    )
except ImportError as e:
    msg = "UOR digest validation module not available: {e}".format(e=e)
    logger.warning(msg)
    DigestValidator = None  # type: ignore
    DigestVerifier = None  # type: ignore
    ValidationResult = None  # type: ignore

try:
    from .mode_access_controls import (
        AccessAction,
        AccessRule,
        AccessDecision,
        ModeAccessController,
        RoleBasedAccessController,
    )
except ImportError as e:
    msg = "UOR mode access controls module not available: {e}".format(e=e)
    logger.warning(msg)
    AccessAction = None  # type: ignore
    AccessRule = None  # type: ignore
    AccessDecision = None  # type: ignore
    ModeAccessController = None  # type: ignore
    RoleBasedAccessController = None  # type: ignore

try:
    from .rate_limiting import (
        RateLimiter,
        SlidingWindowRateLimiter,
        RateLimitInfo,
        UORAPIClient,
    )
except ImportError as e:
    msg = "UOR rate limiting module not available: {e}".format(e=e)
    logger.warning(msg)
    RateLimiter = None  # type: ignore
    SlidingWindowRateLimiter = None  # type: ignore
    RateLimitInfo = None  # type: ignore
    UORAPIClient = None  # type: ignore

try:
    from .secure_keys import (
        KeyMetadata,
        SecureKeyStore,
        KeyManager,
    )
except ImportError as e:
    msg = "UOR secure keys module not available: {e}".format(e=e)
    logger.warning(msg)
    KeyMetadata = None  # type: ignore
    SecureKeyStore = None  # type: ignore
    KeyManager = None  # type: ignore

try:
    from .async_resolution import (
        AsyncObjectResolver,
        AsyncObjectProcessor,
        AsyncBatchValidator,
        resolve_objects_async,
    )
except ImportError as e:
    msg = "UOR async resolution module not available: {e}".format(e=e)
    logger.warning(msg)
    AsyncObjectResolver = None  # type: ignore
    AsyncObjectProcessor = None  # type: ignore
    AsyncBatchValidator = None  # type: ignore
    resolve_objects_async = None  # type: ignore

__all__ = [
    "JsonCase",
    "JsonValue",
    "canonicalize_json",
    "compute_uor_digest",
    "MAX_RECURSION_DEPTH",
    "MAX_ARRAY_LENGTH",
    "MAX_OBJECT_KEYS",
    "bnot",
    "neg",
    "succ",
    "verify_critical_identity",
    "compute_identity_chain",
    "UORIdentityVerifier",
    "UOREnvelope",
    "UORGraphMapper",
    "MerkleNode",
    "MerkleProof",
    "UORMerkleTree",
    "ObjectMode",
    "ObjectVersion",
    "UORObject",
    "ObjectModeEnforcer",
    "LinkRelation",
    "LinkRelationVocabulary",
    "ExecutionRecord",
    "ExecutionRecordEmitter",
    "UORSchemaValidator",
    "GroupOperation",
    "GroupElement",
    "LieGroupOperations",
    "UORObjectTransformation",
    "RecordType",
    "ObjectLocation",
    "UORDNSResolver",
    "DistributedObjectGraph",
    "DNSBasedLinkResolver",
    "TransformationType",
    "Transformation",
    "GroupTheoryOperations",
    "UORObjectMathTransform",
    "SHACLValidator",
    "ConstraintViolation",
    "SHACLValidationResult",
    "RDFConverter",
    "OWLConverter",
    "RDFConversionResult",
    "ObjectSet",
    "HashSetOperations",
    "ObjectSetComparison",
    "UORObjectCache",
    "CacheEntry",
    "CachedObjectAccessor",
    "BatchProcessor",
    "BatchDeduplicator",
    "BatchResult",
    "DigestValidator",
    "DigestVerifier",
    "ValidationResult",
    "AccessAction",
    "AccessRule",
    "AccessDecision",
    "ModeAccessController",
    "RoleBasedAccessController",
    "RateLimiter",
    "SlidingWindowRateLimiter",
    "RateLimitInfo",
    "UORAPIClient",
    "KeyMetadata",
    "SecureKeyStore",
    "KeyManager",
    "AsyncObjectResolver",
    "AsyncObjectProcessor",
    "AsyncBatchValidator",
    "resolve_objects_async",
]
