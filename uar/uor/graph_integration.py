"""UOR object to GraphRAG integration.

Maps UOR object envelopes and links to GraphRAG entities and relations,
enabling graph-based traversal and querying of UOR object collections.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..core.flexible_graphrag import (
    GraphEntity,
    GraphRelation,
    FlexibleGraphRAG,
    SearchStrategy,
)

logger = logging.getLogger(__name__)


@dataclass
class UOREnvelope:
    """UOR object envelope structure."""

    digest: str
    mediaType: str
    mode: str
    schema: str
    attributes: Dict[str, Any]
    links: List[Dict[str, str]]
    content: Any


class UORGraphMapper:
    """Maps UOR objects to GraphRAG entities and relations."""

    def __init__(self, graphrag: Optional[FlexibleGraphRAG] = None):
        """Initialize the UOR graph mapper.

        Args:
            graphrag: Optional FlexibleGraphRAG instance for querying
        """
        self.entity_cache: Dict[str, Any] = {}
        self.relation_cache: Dict[str, Any] = {}
        self.graphrag = graphrag

    def envelope_to_entity(self, envelope: UOREnvelope) -> GraphEntity:
        """Convert UOR envelope to GraphRAG entity.

        Args:
            envelope: UOR object envelope

        Returns:
            GraphRAG entity
        """
        entity = GraphEntity(
            entity_id=envelope.digest,
            entity_type=envelope.schema,
            name=envelope.attributes.get("name", envelope.digest),
            properties={
                "digest": envelope.digest,
                "mediaType": envelope.mediaType,
                "mode": envelope.mode,
                "schema": envelope.schema,
                **envelope.attributes,
            },
        )

        self.entity_cache[envelope.digest] = entity
        return entity

    def links_to_relations(self, envelope: UOREnvelope) -> List[GraphRelation]:
        """Convert UOR links to GraphRAG relations.

        Args:
            envelope: UOR object envelope with links

        Returns:
            List of GraphRAG relations
        """
        relations = []

        for link in envelope.links:
            rel_id = f"{envelope.digest}_{link['rel']}_{link['target']}"
            relation = GraphRelation(
                relation_id=rel_id,
                source_id=envelope.digest,
                target_id=link["target"],
                relation_type=link["rel"],
                properties=link,
            )
            relations.append(relation)

        self.relation_cache[envelope.digest] = relations
        return relations

    def build_object_graph(
        self, envelopes: List[UOREnvelope]
    ) -> Dict[str, Any]:
        """Build complete graph from UOR object collection.

        Args:
            envelopes: List of UOR object envelopes

        Returns:
            Graph with entities and relations
        """
        entities: List[GraphEntity] = []
        relations: List[GraphRelation] = []

        for envelope in envelopes:
            entity = self.envelope_to_entity(envelope)
            entities.append(entity)

            envelope_relations = self.links_to_relations(envelope)
            relations.extend(envelope_relations)

        return {
            "entities": [e.to_dict() for e in entities],
            "relations": [r.to_dict() for r in relations],
            "entity_count": len(entities),
            "relation_count": len(relations),
        }

    def query_by_attributes(
        self, envelopes: List[UOREnvelope], attributes: Dict[str, Any]
    ) -> List[UOREnvelope]:
        """Query envelopes by attribute values.

        Args:
            envelopes: List of UOR object envelopes
            attributes: Attribute key-value pairs to match

        Returns:
            Matching envelopes
        """
        matches = []

        for envelope in envelopes:
            match = True
            for key, value in attributes.items():
                if envelope.attributes.get(key) != value:
                    match = False
                    break
            if match:
                matches.append(envelope)

        return matches

    def trace_derivation_chain(
        self, envelopes: List[UOREnvelope], digest: str, max_depth: int = 10
    ) -> List[str]:
        """Trace derivation chain for an object.

        Args:
            envelopes: List of UOR object envelopes
            digest: Starting object digest
            max_depth: Maximum traversal depth

        Returns:
            List of digests in derivation chain
        """
        chain = [digest]
        visited = {digest}
        current_digest = digest

        for _ in range(max_depth):
            # Find envelope for current digest
            current_envelope = None
            for env in envelopes:
                if env.digest == current_digest:
                    current_envelope = env
                    break

            if not current_envelope:
                break

            # Find "derives-from" links
            for link in current_envelope.links:
                if link.get("rel") == "derives-from":
                    target = link.get("target")
                    if target and target not in visited:
                        chain.append(target)
                        visited.add(target)
                        current_digest = target
                        break
            else:
                break

        return chain

    def integrate_with_graphrag(
        self, envelopes: List[UOREnvelope]
    ) -> FlexibleGraphRAG:
        """Integrate UOR objects with FlexibleGraphRAG for querying.

        Args:
            envelopes: List of UOR object envelopes

        Returns:
            FlexibleGraphRAG instance with UOR objects loaded
        """
        if not self.graphrag:
            from ..core.flexible_graphrag import get_graphrag_instance

            self.graphrag = get_graphrag_instance()

        # Add all UOR objects as entities
        for envelope in envelopes:
            entity = self.envelope_to_entity(envelope)
            # Add to GraphRAG
            self.graphrag.add_entity(
                entity_type=entity.entity_type,
                name=entity.name,
                properties=entity.properties,
            )

        # Add all relations
        for envelope in envelopes:
            relations = self.links_to_relations(envelope)
            for relation in relations:
                self.graphrag.add_relation(
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    relation_type=relation.relation_type,
                    properties=relation.properties,
                )

        logger.info(f"Integrated {len(envelopes)} UOR objects with GraphRAG")
        return self.graphrag

    def query_with_graphrag(
        self,
        query: str,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Query UOR objects using GraphRAG.

        Args:
            query: Query string
            strategy: Search strategy (default HYBRID)
            top_k: Number of results to return

        Returns:
            Query results from GraphRAG

        Raises:
            RuntimeError: If GraphRAG not initialized
        """
        if not self.graphrag:
            raise RuntimeError(
                "GraphRAG not initialized. Call integrate_with_graphrag first."
            )

        return self.graphrag.query_graph(
            query=query,
            strategy=strategy,
            top_k=top_k,
        )
