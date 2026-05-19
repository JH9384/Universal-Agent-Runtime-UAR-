"""Tests for UOR capabilities."""

from uar.uor.identity import (
    bnot,
    neg,
    succ,
    verify_critical_identity,
    compute_identity_chain,
)
from uar.uor.merkle import UORMerkleTree
from uar.uor.object_modes import (
    ObjectMode,
    UORObject,
    ObjectModeEnforcer,
)
from uar.uor.links import LinkRelation, LinkRelationVocabulary
from uar.uor.execution_records import ExecutionRecordEmitter
from uar.uor.schema_validation import UORSchemaValidator
from uar.uor.graph_integration import UORGraphMapper, UOREnvelope


class TestIdentityOperations:
    """Test UOR critical identity operations."""

    def test_bnot(self):
        """Test bitwise NOT operation."""
        assert bnot(42, 8) == 213
        assert bnot(0, 8) == 255
        assert bnot(255, 8) == 0

    def test_neg(self):
        """Test negation operation."""
        assert neg(42, 8) == 214
        assert neg(0, 8) == 0
        assert neg(1, 8) == 255

    def test_succ(self):
        """Test successor operation."""
        assert succ(42, 8) == 43
        assert succ(255, 8) == 0
        assert succ(0, 8) == 1

    def test_verify_critical_identity(self):
        """Test verification of critical identity."""
        assert verify_critical_identity(8) is True
        assert verify_critical_identity(4) is True

    def test_compute_identity_chain(self):
        """Test identity chain computation."""
        chain = compute_identity_chain(42, 8)
        assert chain["x"] == 42
        assert chain["bnot"] == 213
        assert chain["neg_bnot"] == 43
        assert chain["succ"] == 43
        assert chain["valid"] is True


class TestMerkleTree:
    """Test Merkle tree construction."""

    def test_build_tree(self):
        """Test building Merkle tree from digests."""
        tree = UORMerkleTree()
        digests = ["digest1", "digest2", "digest3", "digest4"]
        root = tree.build_tree(digests)
        assert root is not None
        assert tree.get_root_digest() is not None

    def test_generate_proof(self):
        """Test generating Merkle proof."""
        tree = UORMerkleTree()
        digests = ["digest1", "digest2", "digest3", "digest4"]
        tree.build_tree(digests)
        proof = tree.generate_proof("digest1")
        assert proof is not None
        assert proof.target_digest == "digest1"

    def test_verify_proof(self):
        """Test verifying Merkle proof."""
        tree = UORMerkleTree()
        digests = ["digest1", "digest2", "digest3", "digest4"]
        tree.build_tree(digests)
        proof = tree.generate_proof("digest1")
        assert tree.verify_proof(proof) is True

    def test_set_operations(self):
        """Test set operations between trees."""
        tree1 = UORMerkleTree()
        tree1.build_tree(["digest1", "digest2"])

        tree2 = UORMerkleTree()
        tree2.build_tree(["digest2", "digest3"])

        result = tree1.compute_set_operations(tree2)
        assert "union" in result
        assert "intersection" in result
        assert "difference" in result


class TestObjectModes:
    """Test object modes enforcement."""

    def test_validate_mode(self):
        """Test mode validation."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc123",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"key": "value"},
        )
        assert enforcer.validate_mode(obj) is True

    def test_can_modify(self):
        """Test modification permission."""
        enforcer = ObjectModeEnforcer()
        immutable_obj = UORObject(
            digest="sha256:abc123",
            mode=ObjectMode.IMMUTABLE_SINGULAR,
            content={"key": "value"},
        )
        mutable_obj = UORObject(
            digest="sha256:def456",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"key": "value"},
        )
        assert enforcer.can_modify(immutable_obj) is False
        assert enforcer.can_modify(mutable_obj) is True

    def test_update_content(self):
        """Test content update with mode enforcement."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc123",
            mode=ObjectMode.MUTABLE_SINGULAR,
            content={"key": "old_value"},
        )
        updated = enforcer.update_content(obj, {"key": "new_value"})
        assert updated.content == {"key": "new_value"}
        assert updated.version == 2

    def test_array_operations(self):
        """Test mutable array operations."""
        enforcer = ObjectModeEnforcer()
        obj = UORObject(
            digest="sha256:abc123",
            mode=ObjectMode.MUTABLE_ARRAY,
            content="base",
        )
        enforcer.add_array_element(obj, "element1")
        assert len(obj.array_elements) == 1
        assert "element1" in obj.array_elements

        enforcer.remove_array_element(obj, 0)
        assert len(obj.array_elements) == 0


class TestLinkRelations:
    """Test link relation vocabulary."""

    def test_link_relation_constants(self):
        """Test link relation constants."""
        assert LinkRelation.CONTAINS == "contains"
        assert LinkRelation.DERIVES_FROM == "derives-from"
        assert LinkRelation.REFERENCES == "references"

    def test_vocabulary(self):
        """Test link relation vocabulary."""
        vocab = LinkRelationVocabulary()
        assert vocab.is_valid_relation("contains") is True
        assert vocab.is_valid_relation("invalid") is False

    def test_get_description(self):
        """Test getting relation description."""
        vocab = LinkRelationVocabulary()
        desc = vocab.get_description("contains")
        assert len(desc) > 0

    def test_get_inverse(self):
        """Test getting inverse relation."""
        vocab = LinkRelationVocabulary()
        inverse = vocab.get_inverse("contains")
        assert inverse == "contained-by"

    def test_create_link(self):
        """Test creating a link."""
        vocab = LinkRelationVocabulary()
        link = vocab.create_link("contains", "target_digest")
        assert link["rel"] == "contains"
        assert link["target"] == "target_digest"


class TestExecutionRecords:
    """Test execution record emission."""

    def test_create_record(self):
        """Test creating an execution record."""
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

    def test_to_uor_envelope(self):
        """Test converting to UOR envelope."""
        emitter = ExecutionRecordEmitter()
        record = emitter.create_record(
            execution_id="exec_1",
            skill="test_skill",
            input_content={"input": "data"},
            output_content={"output": "result"},
        )
        envelope = emitter.to_uor_envelope(record)
        assert "digest" in envelope
        assert envelope["schema"] == "uar.schema.execution_record.v1"

    def test_query_by_skill(self):
        """Test querying by skill name."""
        emitter = ExecutionRecordEmitter()
        emitter.create_record(
            execution_id="exec_1",
            skill="skill_a",
            input_content={},
            output_content={},
        )
        emitter.create_record(
            execution_id="exec_2",
            skill="skill_b",
            input_content={},
            output_content={},
        )
        results = emitter.query_by_skill("skill_a")
        assert len(results) == 1
        assert results[0].skill == "skill_a"

    def test_get_statistics(self):
        """Test getting execution statistics."""
        emitter = ExecutionRecordEmitter()
        emitter.create_record(
            execution_id="exec_1",
            skill="skill_a",
            input_content={},
            output_content={},
            duration_ms=100.0,
        )
        stats = emitter.get_statistics()
        assert stats["total_executions"] == 1
        assert stats["success_count"] == 1


class TestSchemaValidation:
    """Test schema validation."""

    def test_load_builtin_schemas(self):
        """Test loading built-in schemas."""
        validator = UORSchemaValidator()
        assert "uor.schema.object.v1" in validator.schemas
        assert "uar.schema.execution_record.v1" in validator.schemas

    def test_validate_envelope(self):
        """Test validating UOR envelope."""
        validator = UORSchemaValidator()
        envelope = {
            "digest": "sha256:" + "a" * 64,
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uor.schema.object.v1",
            "content": {},
        }
        is_valid, errors = validator.validate_envelope(envelope)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_envelope(self):
        """Test validating invalid envelope."""
        validator = UORSchemaValidator()
        envelope = {
            "digest": "invalid",
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uor.schema.object.v1",
            "content": {},
        }
        is_valid, errors = validator.validate_envelope(envelope)
        assert is_valid is False
        assert len(errors) > 0

    def test_load_custom_schema(self):
        """Test loading custom schema."""
        validator = UORSchemaValidator()
        custom_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        validator.load_schema("custom.v1", custom_schema)
        assert "custom.v1" in validator.schemas


class TestGraphIntegration:
    """Test graph integration."""

    def test_envelope_to_entity(self):
        """Test converting envelope to entity."""
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

    def test_links_to_relations(self):
        """Test converting links to relations."""
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
        assert relations[0].relation_type == "contains"

    def test_build_object_graph(self):
        """Test building object graph."""
        mapper = UORGraphMapper()
        envelopes = [
            UOREnvelope(
                digest="sha256:" + "a" * 64,
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={"name": "obj1"},
                links=[],
                content={},
            ),
            UOREnvelope(
                digest="sha256:" + "b" * 64,
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={"name": "obj2"},
                links=[],
                content={},
            ),
        ]
        graph = mapper.build_object_graph(envelopes)
        assert graph["entity_count"] == 2
        assert len(graph["entities"]) == 2

    def test_query_by_attributes(self):
        """Test querying by attributes."""
        mapper = UORGraphMapper()
        envelopes = [
            UOREnvelope(
                digest="sha256:" + "a" * 64,
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={"name": "obj1", "type": "document"},
                links=[],
                content={},
            ),
            UOREnvelope(
                digest="sha256:" + "b" * 64,
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={"name": "obj2", "type": "image"},
                links=[],
                content={},
            ),
        ]
        results = mapper.query_by_attributes(envelopes, {"type": "document"})
        assert len(results) == 1
        assert results[0].attributes["name"] == "obj1"

    def test_trace_derivation_chain(self):
        """Test tracing derivation chain."""
        mapper = UORGraphMapper()
        envelopes = [
            UOREnvelope(
                digest="digest3",
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={},
                links=[{"rel": "derives-from", "target": "digest2"}],
                content={},
            ),
            UOREnvelope(
                digest="digest2",
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={},
                links=[{"rel": "derives-from", "target": "digest1"}],
                content={},
            ),
            UOREnvelope(
                digest="digest1",
                mediaType="application/json",
                mode="immutable_singular",
                schema="uor.schema.object.v1",
                attributes={},
                links=[],
                content={},
            ),
        ]
        chain = mapper.trace_derivation_chain(envelopes, "digest3")
        assert "digest3" in chain
        assert "digest2" in chain
        assert "digest1" in chain
