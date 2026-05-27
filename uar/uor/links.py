"""Standardized UOR link relation vocabulary.

Defines standard link relation types for UOR object references,
providing consistent semantics for object relationships.
"""

from typing import Any, Dict, List, Optional


class LinkRelation:
    """Standard UOR link relation types."""

    # Structural relations
    CONTAINS = "contains"
    CONTAINED_BY = "contained-by"
    PART_OF = "part-of"
    HAS_PART = "has-part"

    # Derivation relations
    DERIVES_FROM = "derives-from"
    DERIVED_FROM = "derived-from"
    BASED_ON = "based-on"
    VARIANT_OF = "variant-of"

    # Reference relations
    REFERENCES = "references"
    REFERENCED_BY = "referenced-by"
    CITES = "cites"
    CITED_BY = "cited-by"

    # Dependency relations
    DEPENDS_ON = "depends-on"
    REQUIRED_BY = "required-by"
    REQUIRES = "requires"

    # Version relations
    VERSION_OF = "version-of"
    REPLACES = "replaces"
    REPLACED_BY = "replaced-by"
    PREDECESSOR = "predecessor"
    SUCCESSOR = "successor"

    # Annotation relations
    ANNOTATES = "annotates"
    ANNOTATED_BY = "annotated-by"
    DESCRIBES = "describes"
    DESCRIBED_BY = "described-by"

    # Execution relations
    EXECUTES = "executes"
    EXECUTED_BY = "executed-by"
    PRODUCES = "produces"
    PRODUCED_BY = "produced-by"

    # Schema relations
    CONFORMS_TO = "conforms-to"
    INSTANCE_OF = "instance-of"
    SUBCLASS_OF = "subclass-of"


class LinkRelationVocabulary:
    """Vocabulary for managing link relation semantics."""

    def __init__(self):
        """Initialize the link relation vocabulary."""
        self.relations: Dict[str, Any] = {
            # Structural
            LinkRelation.CONTAINS: {
                "description": "Object contains the target",
                "inverse": LinkRelation.CONTAINED_BY,
            },
            LinkRelation.CONTAINED_BY: {
                "description": "Object is contained by the target",
                "inverse": LinkRelation.CONTAINS,
            },
            LinkRelation.PART_OF: {
                "description": "Object is a part of the target",
                "inverse": LinkRelation.HAS_PART,
            },
            LinkRelation.HAS_PART: {
                "description": "Object has the target as a part",
                "inverse": LinkRelation.PART_OF,
            },
            # Derivation
            LinkRelation.DERIVES_FROM: {
                "description": "Object is derived from the target",
                "inverse": LinkRelation.DERIVED_FROM,
            },
            LinkRelation.DERIVED_FROM: {
                "description": "Object is a derivative of the target",
                "inverse": LinkRelation.DERIVES_FROM,
            },
            LinkRelation.BASED_ON: {
                "description": "Object is based on the target",
                "inverse": None,
            },
            LinkRelation.VARIANT_OF: {
                "description": "Object is a variant of the target",
                "inverse": None,
            },
            # Reference
            LinkRelation.REFERENCES: {
                "description": "Object references the target",
                "inverse": LinkRelation.REFERENCED_BY,
            },
            LinkRelation.REFERENCED_BY: {
                "description": "Object is referenced by the target",
                "inverse": LinkRelation.REFERENCES,
            },
            LinkRelation.CITES: {
                "description": "Object cites the target",
                "inverse": LinkRelation.CITED_BY,
            },
            LinkRelation.CITED_BY: {
                "description": "Object is cited by the target",
                "inverse": LinkRelation.CITES,
            },
            # Dependency
            LinkRelation.DEPENDS_ON: {
                "description": "Object depends on the target",
                "inverse": LinkRelation.REQUIRED_BY,
            },
            LinkRelation.REQUIRED_BY: {
                "description": "Object is required by the target",
                "inverse": LinkRelation.DEPENDS_ON,
            },
            LinkRelation.REQUIRES: {
                "description": "Object requires the target",
                "inverse": None,
            },
            # Version
            LinkRelation.VERSION_OF: {
                "description": "Object is a version of the target",
                "inverse": None,
            },
            LinkRelation.REPLACES: {
                "description": "Object replaces the target",
                "inverse": LinkRelation.REPLACED_BY,
            },
            LinkRelation.REPLACED_BY: {
                "description": "Object is replaced by the target",
                "inverse": LinkRelation.REPLACES,
            },
            LinkRelation.PREDECESSOR: {
                "description": "Object is a predecessor of the target",
                "inverse": LinkRelation.SUCCESSOR,
            },
            LinkRelation.SUCCESSOR: {
                "description": "Object is a successor of the target",
                "inverse": LinkRelation.PREDECESSOR,
            },
            # Annotation
            LinkRelation.ANNOTATES: {
                "description": "Object annotates the target",
                "inverse": LinkRelation.ANNOTATED_BY,
            },
            LinkRelation.ANNOTATED_BY: {
                "description": "Object is annotated by the target",
                "inverse": LinkRelation.ANNOTATES,
            },
            LinkRelation.DESCRIBES: {
                "description": "Object describes the target",
                "inverse": LinkRelation.DESCRIBED_BY,
            },
            LinkRelation.DESCRIBED_BY: {
                "description": "Object is described by the target",
                "inverse": LinkRelation.DESCRIBES,
            },
            # Execution
            LinkRelation.EXECUTES: {
                "description": "Object executes the target",
                "inverse": LinkRelation.EXECUTED_BY,
            },
            LinkRelation.EXECUTED_BY: {
                "description": "Object is executed by the target",
                "inverse": LinkRelation.EXECUTES,
            },
            LinkRelation.PRODUCES: {
                "description": "Object produces the target",
                "inverse": LinkRelation.PRODUCED_BY,
            },
            LinkRelation.PRODUCED_BY: {
                "description": "Object is produced by the target",
                "inverse": LinkRelation.PRODUCES,
            },
            # Schema
            LinkRelation.CONFORMS_TO: {
                "description": "Object conforms to the target schema",
                "inverse": None,
            },
            LinkRelation.INSTANCE_OF: {
                "description": "Object is an instance of the target",
                "inverse": None,
            },
            LinkRelation.SUBCLASS_OF: {
                "description": "Object is a subclass of the target",
                "inverse": None,
            },
        }

    def get_description(self, relation: str) -> str:
        """Get description for a relation type.

        Args:
            relation: Relation type string

        Returns:
            Description string
        """
        return self.relations.get(relation, {}).get("description", "")

    def get_inverse(self, relation: str) -> str:
        """Get inverse relation type.

        Args:
            relation: Relation type string

        Returns:
            Inverse relation type or empty string
        """
        return self.relations.get(relation, {}).get("inverse", "")

    def is_valid_relation(self, relation: str) -> bool:
        """Check if relation type is valid.

        Args:
            relation: Relation type string

        Returns:
            True if relation is valid
        """
        return relation in self.relations

    def get_all_relations(self) -> List[str]:
        """Get all valid relation types.

        Returns:
            List of relation type strings
        """
        return list(self.relations.keys())

    def create_link(
        self, relation: str, target: str, properties: Optional[Dict] = None
    ) -> Dict[str, str]:
        """Create a standardized link.

        Args:
            relation: Relation type
            target: Target digest
            properties: Optional additional properties

        Returns:
            Link dictionary
        """
        if not self.is_valid_relation(relation):
            raise ValueError(f"Invalid relation type: {relation}")

        link = {"rel": relation, "target": target}

        if properties:
            link.update(properties)

        return link
