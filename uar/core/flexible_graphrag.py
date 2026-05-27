"""
Flexible GraphRAG capabilities integration for UAR.

This module provides flexible knowledge graph auto-building with multiple
backends, ontologies, schemas, hybrid semantic search (fulltext, vector,
property graph, RDF/SPARQL), and AI query capabilities, inspired by
flexible-graphrag.

Key features:
- Knowledge graph auto-building from documents
- Ontology and schema support
- Multiple LLM provider support
- Hybrid semantic search (fulltext, vector, property graph, RDF/SPARQL)
- AI query capabilities
- Flexible backend support (Neo4j, Memgraph, etc.)
"""

import logging
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


def _utcnow() -> datetime:
    """Return a naive UTC datetime (no tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.getLogger(__name__).debug(
        "Neo4j not available. Install with: pip install neo4j>=5.0"
    )

# Memgraph is compatible with Neo4j driver, but we flag it separately
# for potential future-specific handling
MEMGRAPH_AVAILABLE = NEO4J_AVAILABLE

logger = logging.getLogger(__name__)


class GraphBackend(Enum):
    """Supported graph database backends."""

    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"
    RDF = "rdf"
    IN_MEMORY = "in_memory"


class SearchStrategy(Enum):
    """Search strategies for graph queries."""

    VECTOR = "vector"
    FULLTEXT = "fulltext"
    PROPERTY_GRAPH = "property_graph"
    RDF_SPARQL = "rdf_sparql"
    HYBRID = "hybrid"


@dataclass
class GraphEntity:
    """Represents an entity in the knowledge graph."""

    entity_id: str
    entity_type: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "properties": self.properties,
            "embeddings": self.embeddings,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class GraphRelation:
    """Represents a relation between entities."""

    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "properties": self.properties,
            "weight": self.weight,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OntologySchema:
    """Schema definition for graph ontology."""

    entity_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relation_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    def add_entity_type(
        self,
        type_name: str,
        properties: Dict[str, str],
        constraints: Optional[Dict[str, Any]] = None,
    ):
        """Add an entity type to the ontology."""
        self.entity_types[type_name] = {
            "properties": properties,
            "constraints": constraints or {},
        }

    def add_relation_type(
        self,
        type_name: str,
        source_types: List[str],
        target_types: List[str],
        properties: Optional[Dict[str, str]] = None,
    ):
        """Add a relation type to the ontology."""
        self.relation_types[type_name] = {
            "source_types": source_types,
            "target_types": target_types,
            "properties": properties or {},
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_types": self.entity_types,
            "relation_types": self.relation_types,
            "constraints": self.constraints,
        }


class FlexibleGraphRAG:
    """Flexible GraphRAG system with multiple backends and search
    strategies."""

    def __init__(
        self,
        backend: GraphBackend = GraphBackend.IN_MEMORY,
        connection_string: str = "",
        ontology: Optional[OntologySchema] = None,
    ):
        self.backend = backend
        self.connection_string = connection_string
        self.ontology = ontology or OntologySchema()
        self.entities: Dict[str, GraphEntity] = {}
        self.relations: Dict[str, GraphRelation] = {}
        self.driver = None

        if backend == GraphBackend.NEO4J and NEO4J_AVAILABLE:
            try:
                self.driver = GraphDatabase.driver(connection_string)
                logger.info(f"Connected to Neo4j: {connection_string}")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
        elif backend == GraphBackend.MEMGRAPH and MEMGRAPH_AVAILABLE:
            try:
                self.driver = GraphDatabase.driver(connection_string)
                logger.info(f"Connected to Memgraph: {connection_string}")
            except Exception as e:
                logger.error(f"Failed to connect to Memgraph: {e}")

    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Database connection closed")

    def add_entity(
        self,
        entity_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
        embeddings: Optional[List[float]] = None,
    ) -> GraphEntity:
        """Add an entity to the graph."""
        entity_id = str(uuid.uuid4())
        entity = GraphEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            properties=properties or {},
            embeddings=embeddings,
        )
        self.entities[entity_id] = entity

        # Also add to Neo4j/Memgraph if backend is Neo4j or Memgraph
        if (
            self.backend in (GraphBackend.NEO4J, GraphBackend.MEMGRAPH)
            and self.driver
        ):
            self._add_entity_to_graph(entity)

        logger.info(f"Added entity: {entity_id} ({entity_type})")
        return entity

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0,
    ) -> GraphRelation:
        """Add a relation to the graph."""
        if source_id not in self.entities or target_id not in self.entities:
            raise ValueError("Source or target entity not found")

        relation_id = str(uuid.uuid4())
        relation = GraphRelation(
            relation_id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties or {},
            weight=weight,
        )
        self.relations[relation_id] = relation

        # Also add to Neo4j/Memgraph if backend is Neo4j or Memgraph
        if (
            self.backend in (GraphBackend.NEO4J, GraphBackend.MEMGRAPH)
            and self.driver
        ):
            self._add_relation_to_graph(relation)

        logger.info(f"Added relation: {relation_id} ({relation_type})")
        return relation

    def _add_entity_to_graph(self, entity: GraphEntity):
        """Add entity to Neo4j or Memgraph database."""
        if not self.driver:
            return

        query = f"""
        MERGE (e:{entity.entity_type} {{id: $id, name: $name}})
        SET e += $properties
        """

        with self.driver.session() as session:
            session.run(
                query,
                id=entity.entity_id,
                name=entity.name,
                properties=entity.properties,
            )

    def _add_relation_to_graph(self, relation: GraphRelation):
        """Add relation to Neo4j or Memgraph database."""
        if not self.driver:
            return

        source = self.entities.get(relation.source_id)
        target = self.entities.get(relation.target_id)
        if not source or not target:
            return

        query = f"""
        MATCH (s:{source.entity_type} {{id: $source_id}})
        MATCH (t:{target.entity_type} {{id: $target_id}})
        MERGE (s)-[r:{relation.relation_type}]->(t)
        SET r += $properties
        """

        with self.driver.session() as session:
            session.run(
                query,
                source_id=relation.source_id,
                target_id=relation.target_id,
                properties=relation.properties,
            )

    def build_graph_from_documents(
        self,
        documents: List[Dict[str, Any]],
        llm_provider: str = "openai",
    ):
        """Build knowledge graph from documents using LLM."""
        logger.info(f"Building graph from {len(documents)} documents")

        # This is a simplified version - in production, you'd use an LLM
        # to extract entities and relations from documents
        for doc in documents:
            text = doc.get("text", "")
            if not text:
                continue

            # Simple entity extraction (in production, use LLM)
            words = text.split()
            for word in words[:10]:  # Limit for demo
                if len(word) > 5:  # Simple heuristic
                    self.add_entity(
                        entity_type="Concept",
                        name=word,
                        properties={"source_document": doc.get("path", "")},
                    )

        # Add some sample relations
        entity_ids = list(self.entities.keys())
        for i in range(len(entity_ids) - 1):
            self.add_relation(
                source_id=entity_ids[i],
                target_id=entity_ids[i + 1],
                relation_type="RELATED_TO",
                weight=0.8,
            )

        logger.info(
            f"Graph built: {len(self.entities)} entities, "
            f"{len(self.relations)} relations"
        )

    def search_vector(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[GraphEntity]:
        """Search using vector similarity."""
        results = []

        # Simple cosine similarity (in production, use proper vector DB)
        for entity in self.entities.values():
            if entity.embeddings and query_embedding:
                similarity = self._cosine_similarity(
                    entity.embeddings,
                    query_embedding,
                )
                if similarity > 0.5:
                    results.append((entity, similarity))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return [entity for entity, _ in results[:top_k]]

    def search_fulltext(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[GraphEntity]:
        """Search using fulltext matching."""
        results = []
        query_lower = query.lower()

        for entity in self.entities.values():
            if query_lower in entity.name.lower():
                results.append(entity)
            elif query_lower in str(entity.properties).lower():
                results.append(entity)

        return results[:top_k]

    def search_property_graph(
        self,
        entity_type: str,
        property_filter: Dict[str, Any],
    ) -> List[GraphEntity]:
        """Search using property graph queries."""
        results = []

        for entity in self.entities.values():
            if entity.entity_type != entity_type:
                continue

            match = True
            for key, value in property_filter.items():
                if entity.properties.get(key) != value:
                    match = False
                    break

            if match:
                results.append(entity)

        return results

    def search_hybrid(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[GraphEntity]:
        """Hybrid search combining multiple strategies."""
        # Combine results from different strategies
        fulltext_results = self.search_fulltext(query, top_k * 2)

        if query_embedding:
            vector_results = self.search_vector(query_embedding, top_k * 2)
        else:
            vector_results = []

        # Deduplicate and score
        scored_results: Dict[str, float] = {}
        for entity in fulltext_results:
            scored_results[entity.entity_id] = (
                scored_results.get(entity.entity_id, 0) + 0.5
            )

        for entity in vector_results:
            scored_results[entity.entity_id] = (
                scored_results.get(entity.entity_id, 0) + 0.5
            )

        # Sort by score and return top_k
        sorted_results = sorted(
            scored_results.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            self.entities[entity_id] for entity_id, _ in sorted_results[:top_k]
        ]

    def _cosine_similarity(
        self, vec1: List[float], vec2: List[float]
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def get_entity_neighbors(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",  # "outgoing", "incoming", "both"
    ) -> List[GraphEntity]:
        """Get neighbors of an entity in the graph."""
        neighbors = []

        for relation in self.relations.values():
            if relation_type and relation.relation_type != relation_type:
                continue

            if direction in ["outgoing", "both"]:
                if relation.source_id == entity_id:
                    neighbor = self.entities.get(relation.target_id)
                    if neighbor:
                        neighbors.append(neighbor)

            if direction in ["incoming", "both"]:
                if relation.target_id == entity_id:
                    neighbor = self.entities.get(relation.source_id)
                    if neighbor:
                        neighbors.append(neighbor)

        return neighbors

    def query_graph(
        self,
        query: str,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Query the knowledge graph."""
        results = []

        if strategy == SearchStrategy.VECTOR:
            # Would need query embedding
            pass
        elif strategy == SearchStrategy.FULLTEXT:
            results = self.search_fulltext(query, top_k)
        elif strategy == SearchStrategy.PROPERTY_GRAPH:
            # Would need property filter
            pass
        elif strategy == SearchStrategy.RDF_SPARQL:
            # Would need SPARQL query
            pass
        else:  # HYBRID
            results = self.search_hybrid(query, top_k=top_k)

        return {
            "query": query,
            "strategy": strategy.value,
            "results": [entity.to_dict() for entity in results],
            "result_count": len(results),
        }

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the graph."""
        entity_types: Dict[str, int] = {}
        for entity in self.entities.values():
            entity_types[entity.entity_type] = (
                entity_types.get(entity.entity_type, 0) + 1
            )

        relation_types: Dict[str, int] = {}
        for relation in self.relations.values():
            relation_types[relation.relation_type] = (
                relation_types.get(relation.relation_type, 0) + 1
            )

        return {
            "entity_count": len(self.entities),
            "relation_count": len(self.relations),
            "entity_types": entity_types,
            "relation_types": relation_types,
            "backend": self.backend.value,
            "ontology": self.ontology.to_dict(),
        }


# Global GraphRAG instance
_graphrag_instance: Optional[FlexibleGraphRAG] = None


def get_graphrag_instance(
    backend: GraphBackend = GraphBackend.IN_MEMORY,
    connection_string: str = "",
    ontology: Optional[OntologySchema] = None,
) -> FlexibleGraphRAG:
    """Get or create the global GraphRAG instance."""
    global _graphrag_instance
    if _graphrag_instance is None:
        _graphrag_instance = FlexibleGraphRAG(
            backend=backend,
            connection_string=connection_string,
            ontology=ontology,
        )
    return _graphrag_instance


def create_standard_ontology() -> OntologySchema:
    """Create a standard ontology for common use cases."""
    ontology = OntologySchema()

    # Entity types
    ontology.add_entity_type(
        "Document",
        properties={"path": "string", "title": "string", "content": "text"},
    )
    ontology.add_entity_type(
        "Concept",
        properties={"name": "string", "definition": "text"},
    )
    ontology.add_entity_type(
        "Person",
        properties={"name": "string", "role": "string"},
    )
    ontology.add_entity_type(
        "Organization",
        properties={"name": "string", "type": "string"},
    )

    # Relation types
    ontology.add_relation_type(
        "MENTIONS",
        source_types=["Document"],
        target_types=["Concept", "Person", "Organization"],
    )
    ontology.add_relation_type(
        "RELATED_TO",
        source_types=["Concept"],
        target_types=["Concept"],
    )
    ontology.add_relation_type(
        "BELONGS_TO",
        source_types=["Person"],
        target_types=["Organization"],
    )

    return ontology
