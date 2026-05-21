"""
Tests for Flexible GraphRAG integration.
"""

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


def test_graph_entity_creation():
    """Test creating a graph entity."""
    entity = GraphEntity(
        entity_id="test_entity",
        entity_type="Concept",
        name="Test Concept",
        properties={"description": "A test concept"},
    )
    
    assert entity.entity_id == "test_entity"
    assert entity.entity_type == "Concept"
    assert entity.name == "Test Concept"


def test_graph_relation_creation():
    """Test creating a graph relation."""
    relation = GraphRelation(
        relation_id="test_relation",
        source_id="entity1",
        target_id="entity2",
        relation_type="RELATED_TO",
        weight=0.8,
    )
    
    assert relation.relation_id == "test_relation"
    assert relation.source_id == "entity1"
    assert relation.target_id == "entity2"
    assert relation.relation_type == "RELATED_TO"
    assert relation.weight == 0.8


def test_ontology_schema_creation():
    """Test creating an ontology schema."""
    ontology = OntologySchema()
    
    ontology.add_entity_type(
        "Person",
        properties={"name": "string", "age": "integer"},
    )
    
    ontology.add_relation_type(
        "KNOWS",
        source_types=["Person"],
        target_types=["Person"],
        properties={"since": "date"},
    )
    
    assert "Person" in ontology.entity_types
    assert "KNOWS" in ontology.relation_types


def test_flexible_graphrag_creation():
    """Test creating a FlexibleGraphRAG instance."""
    graphrag = FlexibleGraphRAG(
        backend=GraphBackend.IN_MEMORY,
    )
    
    assert graphrag.backend == GraphBackend.IN_MEMORY
    assert len(graphrag.entities) == 0
    assert len(graphrag.relations) == 0


def test_flexible_graphrag_add_entity():
    """Test adding an entity to the graph."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    entity = graphrag.add_entity(
        entity_type="Concept",
        name="Test Concept",
        properties={"description": "A test"},
    )
    
    assert entity.entity_id in graphrag.entities
    assert entity.name == "Test Concept"


def test_flexible_graphrag_add_relation():
    """Test adding a relation to the graph."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    entity1 = graphrag.add_entity(
        entity_type="Concept",
        name="Concept 1",
    )
    entity2 = graphrag.add_entity(
        entity_type="Concept",
        name="Concept 2",
    )
    
    relation = graphrag.add_relation(
        source_id=entity1.entity_id,
        target_id=entity2.entity_id,
        relation_type="RELATED_TO",
    )
    
    assert relation.relation_id in graphrag.relations
    assert relation.source_id == entity1.entity_id
    assert relation.target_id == entity2.entity_id


def test_flexible_graphrag_search_fulltext():
    """Test fulltext search in the graph."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    graphrag.add_entity(
        entity_type="Concept",
        name="Python Programming",
        properties={"description": "A programming language"},
    )
    graphrag.add_entity(
        entity_type="Concept",
        name="JavaScript",
        properties={"description": "Web scripting language"},
    )
    
    results = graphrag.search_fulltext("Python", top_k=5)
    
    assert len(results) == 1
    assert "Python" in results[0].name


def test_flexible_graphrag_search_property_graph():
    """Test property graph search."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    graphrag.add_entity(
        entity_type="Person",
        name="John",
        properties={"age": 30},
    )
    graphrag.add_entity(
        entity_type="Person",
        name="Jane",
        properties={"age": 25},
    )
    
    results = graphrag.search_property_graph(
        entity_type="Person",
        property_filter={"age": 30},
    )
    
    assert len(results) == 1
    assert results[0].name == "John"


def test_flexible_graphrag_get_neighbors():
    """Test getting entity neighbors."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    entity1 = graphrag.add_entity(entity_type="Concept", name="A")
    entity2 = graphrag.add_entity(entity_type="Concept", name="B")
    entity3 = graphrag.add_entity(entity_type="Concept", name="C")
    
    graphrag.add_relation(
        source_id=entity1.entity_id,
        target_id=entity2.entity_id,
        relation_type="RELATED_TO",
    )
    graphrag.add_relation(
        source_id=entity1.entity_id,
        target_id=entity3.entity_id,
        relation_type="RELATED_TO",
    )
    
    neighbors = graphrag.get_entity_neighbors(
        entity1.entity_id,
        direction="outgoing",
    )
    
    assert len(neighbors) == 2


def test_flexible_graphrag_query_graph():
    """Test querying the graph."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    graphrag.add_entity(
        entity_type="Concept",
        name="Python Programming",
        properties={"description": "A programming language"},
    )
    
    result = graphrag.query_graph(
        query="Python",
        strategy=SearchStrategy.FULLTEXT,
    )
    
    assert result["query"] == "Python"
    assert result["strategy"] == "fulltext"
    assert result["result_count"] == 1


def test_flexible_graphrag_get_stats():
    """Test getting graph statistics."""
    graphrag = FlexibleGraphRAG(backend=GraphBackend.IN_MEMORY)
    
    graphrag.add_entity(entity_type="Concept", name="A")
    graphrag.add_entity(entity_type="Concept", name="B")
    graphrag.add_relation(
        source_id=list(graphrag.entities.keys())[0],
        target_id=list(graphrag.entities.keys())[1],
        relation_type="RELATED_TO",
    )
    
    stats = graphrag.get_graph_stats()
    
    assert stats["entity_count"] == 2
    assert stats["relation_count"] == 1
    assert stats["backend"] == "in_memory"


def test_get_graphrag_singleton():
    """Test global GraphRAG singleton."""
    graphrag1 = get_graphrag_instance()
    graphrag2 = get_graphrag_instance()
    
    assert graphrag1 is graphrag2


def test_create_standard_ontology():
    """Test creating a standard ontology."""
    ontology = create_standard_ontology()
    
    assert "Document" in ontology.entity_types
    assert "Concept" in ontology.entity_types
    assert "Person" in ontology.entity_types
    assert "Organization" in ontology.entity_types
    assert "MENTIONS" in ontology.relation_types
    assert "RELATED_TO" in ontology.relation_types
