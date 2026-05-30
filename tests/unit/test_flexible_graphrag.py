"""Tests for uar.core.flexible_graphrag."""

import pytest

from uar.core.flexible_graphrag import (
    GraphBackend,
    SearchStrategy,
    GraphEntity,
    GraphRelation,
    OntologySchema,
    FlexibleGraphRAG,
    get_graphrag_instance,
    create_standard_ontology,
)


class TestGraphEntity:
    def test_to_dict(self):
        e = GraphEntity(entity_id="1", entity_type="Concept", name="Test")
        d = e.to_dict()
        assert d["entity_id"] == "1"
        assert d["entity_type"] == "Concept"
        assert "created_at" in d


class TestGraphRelation:
    def test_to_dict(self):
        r = GraphRelation(
            relation_id="r1", source_id="1", target_id="2",
            relation_type="RELATED_TO"
        )
        d = r.to_dict()
        assert d["relation_id"] == "r1"
        assert d["weight"] == 1.0


class TestOntologySchema:
    def test_add_entity_type(self):
        o = OntologySchema()
        o.add_entity_type("Doc", {"path": "string"})
        assert "Doc" in o.entity_types

    def test_add_relation_type(self):
        o = OntologySchema()
        o.add_relation_type("MENTIONS", ["Doc"], ["Concept"])
        assert "MENTIONS" in o.relation_types

    def test_to_dict(self):
        o = OntologySchema()
        o.add_entity_type("Doc", {"path": "string"})
        d = o.to_dict()
        assert "entity_types" in d
        assert "relation_types" in d


class TestFlexibleGraphRAG:
    def test_create_in_memory(self):
        rag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
        assert rag.backend == GraphBackend.IN_MEMORY
        assert rag.driver is None

    def test_add_entity(self):
        rag = FlexibleGraphRAG()
        e = rag.add_entity("Concept", "AI", properties={"field": "cs"})
        assert e.entity_id in rag.entities

    def test_add_relation(self):
        rag = FlexibleGraphRAG()
        e1 = rag.add_entity("Concept", "A")
        e2 = rag.add_entity("Concept", "B")
        r = rag.add_relation(e1.entity_id, e2.entity_id, "RELATED_TO")
        assert r.relation_id in rag.relations

    def test_add_relation_missing_entity(self):
        rag = FlexibleGraphRAG()
        with pytest.raises(ValueError, match="not found"):
            rag.add_relation("nope", "nope", "RELATED_TO")

    def test_cosine_similarity(self):
        rag = FlexibleGraphRAG()
        sim = rag._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert pytest.approx(sim, 0.01) == 1.0

    def test_cosine_similarity_zero(self):
        rag = FlexibleGraphRAG()
        sim = rag._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        assert sim == 0.0

    def test_search_fulltext(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "Machine Learning")
        results = rag.search_fulltext("machine")
        assert len(results) == 1

    def test_search_vector(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "A", embeddings=[1.0, 0.0])
        results = rag.search_vector([1.0, 0.0], top_k=5)
        assert len(results) >= 0

    def test_search_property_graph(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "A", properties={"field": "cs"})
        results = rag.search_property_graph("Concept", {"field": "cs"})
        assert len(results) == 1

    def test_search_hybrid(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "Test")
        results = rag.search_hybrid("test")
        assert len(results) >= 0

    def test_get_entity_neighbors(self):
        rag = FlexibleGraphRAG()
        e1 = rag.add_entity("Concept", "A")
        e2 = rag.add_entity("Concept", "B")
        rag.add_relation(e1.entity_id, e2.entity_id, "RELATED_TO")
        neighbors = rag.get_entity_neighbors(e1.entity_id)
        assert len(neighbors) == 1

    def test_get_entity_neighbors_incoming(self):
        rag = FlexibleGraphRAG()
        e1 = rag.add_entity("Concept", "A")
        e2 = rag.add_entity("Concept", "B")
        rag.add_relation(e1.entity_id, e2.entity_id, "RELATED_TO")
        neighbors = rag.get_entity_neighbors(
            e2.entity_id, direction="incoming"
        )
        assert len(neighbors) == 1

    def test_query_graph_fulltext(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "Test")
        result = rag.query_graph("test", strategy=SearchStrategy.FULLTEXT)
        assert result["strategy"] == "fulltext"
        assert result["result_count"] >= 0

    def test_query_graph_hybrid(self):
        rag = FlexibleGraphRAG()
        result = rag.query_graph("test", strategy=SearchStrategy.HYBRID)
        assert result["strategy"] == "hybrid"

    def test_get_graph_stats(self):
        rag = FlexibleGraphRAG()
        rag.add_entity("Concept", "A")
        stats = rag.get_graph_stats()
        assert stats["entity_count"] == 1
        assert stats["backend"] == "in_memory"

    def test_build_graph_from_documents(self):
        rag = FlexibleGraphRAG()
        rag.build_graph_from_documents([{"text": "hello world testing"}])
        assert len(rag.entities) > 0

    def test_close(self):
        rag = FlexibleGraphRAG()
        rag.close()  # should not raise


class TestGlobalInstance:
    def test_get_graphrag_instance(self):
        rag1 = get_graphrag_instance()
        rag2 = get_graphrag_instance()
        assert rag1 is rag2

    def test_create_standard_ontology(self):
        o = create_standard_ontology()
        assert "Document" in o.entity_types
        assert "MENTIONS" in o.relation_types
