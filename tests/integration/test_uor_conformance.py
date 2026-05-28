"""UOR Foundation conformance tests.

Tests to validate that UAR's UOR implementation conforms to
UOR Foundation specifications and best practices.
"""

from uar.uor.bounded_json import compute_uor_digest, canonicalize_json
from uar.uor.identity import bnot, neg, succ
from uar.uor.object_modes import ObjectMode, UORObject, ObjectModeEnforcer
from uar.uor.links import LinkRelationVocabulary
from uar.uor.schema_validation import UORSchemaValidator


class TestCanonicalizationConformance:
    """Test conformance with UOR canonicalization specification."""

    def test_jcs_canonicalization(self):
        """Test JCS-RFC8785 canonicalization compliance."""
        # Test that canonicalization is deterministic
        obj1 = {"a": 1, "b": 2}
        obj2 = {"b": 2, "a": 1}
        canonical1 = canonicalize_json(obj1)
        canonical2 = canonicalize_json(obj2)
        assert canonical1 == canonical2

    def test_digest_uniqueness(self):
        """Test that different content produces different digests."""
        obj1 = {"value": "test"}
        obj2 = {"value": "different"}
        digest1 = compute_uor_digest(obj1)
        digest2 = compute_uor_digest(obj2)
        assert digest1 != digest2

    def test_digest_determinism(self):
        """Test that same content always produces same digest."""
        obj = {"value": "test", "nested": {"key": "value"}}
        digest1 = compute_uor_digest(obj)
        digest2 = compute_uor_digest(obj)
        assert digest1 == digest2

    def test_unicode_normalization(self):
        """Test Unicode NFC normalization compliance."""
        # Test that composed and decomposed forms normalize to same
        obj1 = {"value": "café"}
        obj2 = {"value": "cafe\u0301"}
        digest1 = compute_uor_digest(obj1)
        digest2 = compute_uor_digest(obj2)
        assert digest1 == digest2

    def test_case_sensitivity(self):
        """Test CT-T case sensitivity compliance."""
        obj1 = {"Value": "test"}
        obj2 = {"value": "test"}
        digest1 = compute_uor_digest(obj1)
        digest2 = compute_uor_digest(obj2)
        assert digest1 != digest2


class TestIdentityOperationsConformance:
    """Test conformance with UOR critical identity operations."""

    def test_ring_modulus(self):
        """Test operations respect n-bit ring modulus."""
        n = 8
        max_val = 2**n - 1

        # Test that operations stay within ring
        x = max_val
        result = succ(x, n)
        assert result == 0  # Wrap around

    def test_critical_identity_property(self):
        """Test neg(bnot(x)) = succ(x) property."""
        for n in [8, 16, 32]:
            for x in [0, 1, 42, 2**n - 1, 2**n - 2]:
                result = neg(bnot(x, n), n)
                expected = succ(x, n)
                assert result == expected, f"Failed for x={x}, n={n}"

    def test_identity_chain_consistency(self):
        """Test identity chain produces consistent results."""
        from uar.uor.identity import compute_identity_chain

        chain = compute_identity_chain(42, 8)
        assert chain["valid"] is True
        assert chain["neg_bnot"] == chain["succ"]


class TestObjectModesConformance:
    """Test conformance with UOR object mode specifications."""

    def test_immutable_mode_enforcement(self):
        """Test immutable singular mode prevents modification."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:" + "a" * 64,
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"original": "value"},
        )
        assert enforcer.can_modify(obj) is False

    def test_mutable_mode_allows_modification(self):
        """Test mutable singular mode allows modification."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:" + "a" * 64,
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"original": "value"},
        )
        assert enforcer.can_modify(obj) is True

    def test_version_tracking(self):
        """Test that modifications increment version."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:" + "a" * 64,
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"value": "original"},
            version=1,
        )
        updated = enforcer.update_content(obj, {"value": "new"})
        assert updated.version == 2

    def test_mutable_array_enforcement(self):
        """Test mutable array mode allows element operations."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:" + "a" * 64,
            mode=ObjectMode.MUTABLE_ARRAY,
            content="base",
            array_elements=[],
        )
        enforcer.add_array_element(obj, "element1")
        assert len(obj.array_elements) == 1
        enforcer.remove_array_element(obj, 0)
        assert len(obj.array_elements) == 0


class TestLinkRelationsConformance:
    """Test conformance with UOR link relation vocabulary."""

    def test_standard_relation_types(self):
        """Test standard UOR relation types are available."""
        vocab = LinkRelationVocabulary()

        # Test structural relations
        assert vocab.is_valid_relation("contains")
        assert vocab.is_valid_relation("contained-by")

        # Test derivation relations
        assert vocab.is_valid_relation("derives-from")
        assert vocab.is_valid_relation("derived-from")

        # Test reference relations
        assert vocab.is_valid_relation("references")
        assert vocab.is_valid_relation("referenced-by")

    def test_inverse_relation_consistency(self):
        """Test that inverse relations are consistent."""
        vocab = LinkRelationVocabulary()

        assert vocab.get_inverse("contains") == "contained-by"
        assert vocab.get_inverse("derives-from") == "derived-from"
        assert vocab.get_inverse("references") == "referenced-by"

    def test_link_structure_compliance(self):
        """Test link structure follows UOR specification."""
        vocab = LinkRelationVocabulary()
        link = vocab.create_link("contains", "target_digest")

        assert "rel" in link
        assert "target" in link
        assert link["rel"] == "contains"
        assert link["target"] == "target_digest"


class TestSchemaValidationConformance:
    """Test conformance with UOR schema validation."""

    def test_envelope_schema_compliance(self):
        """Test envelope schema follows UOR specification."""
        validator = UORSchemaValidator()
        envelope = {
            "digest": "sha256:" + "a" * 64,
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uor.schema.object.v1",
            "attributes": {},
            "links": [],
            "content": {},
        }
        is_valid, errors = validator.validate_envelope(envelope)
        assert is_valid is True
        assert len(errors) == 0

    def test_digest_pattern_validation(self):
        """Test digest pattern matches UOR specification."""
        validator = UORSchemaValidator()

        # Valid digest
        valid_envelope = {
            "digest": "sha256:" + "a" * 64,
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uor.schema.object.v1",
            "content": {},
        }
        is_valid, _ = validator.validate_envelope(valid_envelope)
        assert is_valid is True

        # Invalid digest
        invalid_envelope = {
            "digest": "invalid",
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uor.schema.object.v1",
            "content": {},
        }
        is_valid, errors = validator.validate_envelope(invalid_envelope)
        assert is_valid is False

    def test_mode_enum_validation(self):
        """Test mode enum matches UOR specification."""
        validator = UORSchemaValidator()

        valid_modes = [
            "immutable_singular",
            "mutable_singular",
            "mutable_array",
        ]

        for mode in valid_modes:
            envelope = {
                "digest": "sha256:" + "a" * 64,
                "mediaType": "application/json",
                "mode": mode,
                "schema": "uor.schema.object.v1",
                "content": {},
            }
            is_valid, _ = validator.validate_envelope(envelope)
            assert is_valid is True


class TestExecutionRecordConformance:
    """Test conformance with execution record specification."""

    def test_execution_record_structure(self):
        """Test execution record follows UOR specification."""
        from uar.uor.execution_records import ExecutionRecordEmitter

        emitter = ExecutionRecordEmitter()
        record = emitter.create_record(
            execution_id="exec_1",
            skill="test_skill",
            input_content={"input": "data"},
            output_content={"output": "result"},
        )

        assert record.execution_id == "exec_1"
        assert record.skill == "test_skill"
        assert record.status == "success"
        assert record.input_digest is not None
        assert record.output_digest is not None

    def test_execution_record_envelope_conversion(self):
        """Test execution record converts to valid UOR envelope."""
        from uar.uor.execution_records import ExecutionRecordEmitter

        emitter = ExecutionRecordEmitter()
        record = emitter.create_record(
            execution_id="exec_1",
            skill="test_skill",
            input_content={},
            output_content={},
        )
        envelope = emitter.to_uor_envelope(record)

        assert "digest" in envelope
        assert envelope["schema"] == "uar.schema.execution_record.v1"
        assert "execution_id" in envelope["content"]


class TestMerkleTreeConformance:
    """Test conformance with Merkle tree specification."""

    def test_merkle_root_determinism(self):
        """Test Merkle root is deterministic."""
        from uar.uor.merkle import UORMerkleTree

        tree1 = UORMerkleTree()
        tree2 = UORMerkleTree()
        digests = ["digest1", "digest2", "digest3"]

        root1 = tree1.build_tree(digests)
        root2 = tree2.build_tree(digests)
        assert root1 == root2

    def test_merkle_proof_verification(self):
        """Test Merkle proof verification works correctly."""
        from uar.uor.merkle import UORMerkleTree

        tree = UORMerkleTree()
        digests = ["digest1", "digest2", "digest3", "digest4"]
        tree.build_tree(digests)

        proof = tree.generate_proof("digest1")
        assert tree.verify_proof(proof) is True

        # Test invalid proof
        proof.target_digest = "invalid_digest"
        assert tree.verify_proof(proof) is False


class TestGraphIntegrationConformance:
    """Test conformance with graph integration specification."""

    def test_entity_structure(self):
        """Test entity structure follows GraphRAG specification."""
        from uar.uor.graph_integration import UORGraphMapper, UOREnvelope

        mapper = UORGraphMapper()
        envelope = UOREnvelope(
            digest="sha256:" + "a" * 64,
            mediaType="application/json",
            mode="immutable_singular",
            schema="uor.schema.object.v1",
            attributes={"name": "test"},
            links=[],
            content={},
        )
        entity = mapper.envelope_to_entity(envelope)

        assert entity.entity_id == envelope.digest
        assert entity.entity_type == envelope.schema
        assert entity.name is not None
        assert isinstance(entity.properties, dict)

    def test_relation_structure(self):
        """Test relation structure follows GraphRAG specification."""
        from uar.uor.graph_integration import UORGraphMapper, UOREnvelope

        mapper = UORGraphMapper()
        envelope = UOREnvelope(
            digest="sha256:" + "a" * 64,
            mediaType="application/json",
            mode="immutable_singular",
            schema="uor.schema.object.v1",
            attributes={},
            links=[{"rel": "contains", "target": "target_digest"}],
            content={},
        )
        relations = mapper.links_to_relations(envelope)

        assert len(relations) == 1
        assert relations[0].source_id == envelope.digest
        assert relations[0].target_id == "target_digest"
        assert relations[0].relation_type == "contains"


class TestLieGroupsConformance:
    """Test conformance with Lie groups mathematical foundations."""

    def test_group_closure(self):
        """Test group operations maintain closure property."""
        from uar.uor.lie_groups import LieGroupOperations

        ops = LieGroupOperations()
        angle = 1.57  # ~90 degrees
        matrix1 = ops.rotation_matrix(angle)
        matrix2 = ops.rotation_matrix(angle)

        # Composition should stay in group
        composed = ops.compose_matrices(matrix1, matrix2)
        assert composed is not None
        assert len(composed) == 2
        assert len(composed[0]) == 2

    def test_identity_element(self):
        """Test identity element exists in group."""
        from uar.uor.lie_groups import LieGroupOperations

        ops = LieGroupOperations()
        identity = ops.rotation_matrix(0)

        # Identity matrix should be [[1, 0], [0, 1]]
        assert identity[0][0] == 1.0
        assert identity[0][1] == 0.0
        assert identity[1][0] == 0.0
        assert identity[1][1] == 1.0

    def test_inverse_element(self):
        """Test every element has an inverse."""
        from uar.uor.lie_groups import LieGroupOperations

        ops = LieGroupOperations()
        matrix = ops.rotation_matrix(1.57)
        inverse = ops.invert_matrix(matrix)

        # Matrix * inverse should equal identity
        composed = ops.compose_matrices(matrix, inverse)
        # Check diagonal elements are close to 1
        assert abs(composed[0][0] - 1.0) < 0.01
        assert abs(composed[1][1] - 1.0) < 0.01

    def test_associativity(self):
        """Test group operations are associative."""
        from uar.uor.lie_groups import LieGroupOperations

        ops = LieGroupOperations()
        m1 = ops.rotation_matrix(0.5)
        m2 = ops.rotation_matrix(0.5)
        m3 = ops.rotation_matrix(0.5)

        # (m1 * m2) * m3 == m1 * (m2 * m3)
        left = ops.compose_matrices(ops.compose_matrices(m1, m2), m3)
        right = ops.compose_matrices(m1, ops.compose_matrices(m2, m3))

        for i in range(len(left)):
            for j in range(len(left[0])):
                assert abs(left[i][j] - right[i][j]) < 0.01
