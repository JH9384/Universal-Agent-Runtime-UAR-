"""
Example: Using Flexible GraphRAG for knowledge graph RAG.

This example demonstrates how to use the Flexible GraphRAG integration
for knowledge graph-based retrieval-augmented generation with multiple
backends and hybrid search strategies.
"""

from uar.core.flexible_graphrag import (
    FlexibleGraphRAG,
    GraphBackend,
    SearchStrategy,
    OntologySchema,
    create_standard_ontology,
    get_graphrag_instance,
)


def example_basic_graphrag():
    """Basic GraphRAG usage with in-memory backend."""
    print("=== Basic GraphRAG ===")

    ontology = create_standard_ontology()
    graphrag = FlexibleGraphRAG(
        backend=GraphBackend.IN_MEMORY, ontology=ontology
    )

    # Add entities
    entity1 = graphrag.add_entity(
        entity_type="Concept",
        name="Python Programming",
        properties={"description": "A programming language"},
    )
    entity2 = graphrag.add_entity(
        entity_type="Person",
        name="Guido van Rossum",
        properties={"role": "Creator of Python"},
    )

    # Add relation
    graphrag.add_relation(
        source_id=entity1.entity_id,
        target_id=entity2.entity_id,
        relation_type="CREATED_BY",
    )

    # Query
    result = graphrag.query_graph("Python", strategy=SearchStrategy.FULLTEXT)
    print(f"Query result: {result['result_count']} results")
    print(f"Results: {result['results']}")


def example_hybrid_search():
    """Hybrid search with multiple strategies."""
    print("\n=== Hybrid Search ===")

    graphrag = get_graphrag_instance(backend=GraphBackend.IN_MEMORY)

    # Add sample data
    graphrag.add_entity(
        entity_type="Document",
        name="AI Research Paper",
        properties={"year": 2024, "topic": "Machine Learning"},
    )
    graphrag.add_entity(
        entity_type="Concept",
        name="Neural Networks",
        properties={"type": "ML Architecture"},
    )

    # Try different search strategies
    strategies = [
        SearchStrategy.VECTOR,
        SearchStrategy.FULLTEXT,
        SearchStrategy.HYBRID,
    ]

    for strategy in strategies:
        result = graphrag.query_graph(
            "Neural Networks",
            strategy=strategy,
            top_k=3,
        )
        print(f"{strategy.value}: {result['result_count']} results")


def example_graph_statistics():
    """Get graph statistics."""
    print("\n=== Graph Statistics ===")

    graphrag = get_graphrag_instance(backend=GraphBackend.IN_MEMORY)

    # Add some data
    for i in range(5):
        graphrag.add_entity(entity_type="Concept", name=f"Concept {i}")

    stats = graphrag.get_graph_stats()
    print(f"Entity count: {stats['entity_count']}")
    print(f"Relation count: {stats['relation_count']}")
    print(f"Backend: {stats['backend']}")


def example_ontology():
    """Custom ontology definition."""
    print("\n=== Custom Ontology ===")

    ontology = OntologySchema()

    # Define entity types
    ontology.add_entity_type(
        "Product",
        properties={"name": "string", "price": "float", "category": "string"},
    )
    ontology.add_entity_type(
        "Customer",
        properties={"name": "string", "email": "string"},
    )

    # Define relation types
    ontology.add_relation_type(
        "PURCHASED",
        source_types=["Customer"],
        target_types=["Product"],
        properties={"date": "date", "quantity": "int"},
    )

    print(f"Entity types: {list(ontology.entity_types.keys())}")
    print(f"Relation types: {list(ontology.relation_types.keys())}")


if __name__ == "__main__":
    example_basic_graphrag()
    example_hybrid_search()
    example_graph_statistics()
    example_ontology()
