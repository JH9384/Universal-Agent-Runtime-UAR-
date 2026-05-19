"""UOR object modes enforcement.

Implements the three UOR object modes: Immutable Singular, Mutable Singular,
and Mutable Array with mode-specific behaviors and transition rules.
"""

import logging
from typing import Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

from .bounded_json import compute_uor_digest

logger = logging.getLogger(__name__)


class ObjectMode:
    """UOR object mode constants."""

    IMMUTABLE_SINGULAR = "immutable_singular"
    MUTABLE_SINGULAR = "mutable_singular"
    MUTABLE_ARRAY = "mutable_array"


@dataclass
class ObjectVersion:
    """Version history for mutable objects."""

    version: int
    digest: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UORObject:
    """UOR object with mode enforcement."""

    digest: str
    mode: str
    content: Any
    attributes: Dict[str, Any] = field(default_factory=dict)
    links: List[Dict[str, str]] = field(default_factory=list)
    schema: str = "uor.schema.object.v1"
    mediaType: str = "application/json"

    # Mutable object fields
    version: int = 1
    version_history: List[ObjectVersion] = field(default_factory=list)
    array_elements: List[Any] = field(default_factory=list)


class ObjectModeEnforcer:
    """Enforces UOR object mode rules."""

    def __init__(self):
        """Initialize the object mode enforcer."""
        self.mode_transitions = {
            ObjectMode.IMMUTABLE_SINGULAR: [],  # No transitions allowed
            ObjectMode.MUTABLE_SINGULAR: [ObjectMode.MUTABLE_SINGULAR],
            ObjectMode.MUTABLE_ARRAY: [ObjectMode.MUTABLE_ARRAY],
        }

    def validate_mode(self, obj: UORObject) -> bool:
        """Validate object mode is supported.

        Args:
            obj: UOR object to validate

        Returns:
            True if mode is valid
        """
        return obj.mode in [
            ObjectMode.IMMUTABLE_SINGULAR,
            ObjectMode.MUTABLE_SINGULAR,
            ObjectMode.MUTABLE_ARRAY,
        ]

    def can_modify(self, obj: UORObject) -> bool:
        """Check if object can be modified based on mode.

        Args:
            obj: UOR object

        Returns:
            True if modification is allowed
        """
        return obj.mode in [
            ObjectMode.MUTABLE_SINGULAR,
            ObjectMode.MUTABLE_ARRAY,
        ]

    def can_transition_mode(
        self, obj: UORObject, new_mode: str
    ) -> bool:
        """Check if mode transition is allowed.

        Args:
            obj: UOR object
            new_mode: Target mode

        Returns:
            True if transition is allowed
        """
        if new_mode not in self.mode_transitions.get(obj.mode, []):
            return False
        return True

    def update_content(
        self, obj: UORObject, new_content: Any, preserve_history: bool = True
    ) -> UORObject:
        """Update object content with mode enforcement.

        Args:
            obj: UOR object to update
            new_content: New content
            preserve_history: Whether to preserve version history

        Returns:
            Updated object

        Raises:
            ValueError: If modification not allowed by mode
        """
        if not self.can_modify(obj):
            raise ValueError(
                f"Cannot modify object in mode {obj.mode}. "
                "Only mutable modes allow modifications."
            )

        if preserve_history:
            # Save current version
            version = ObjectVersion(
                version=obj.version,
                digest=obj.digest,
                content=obj.content,
            )
            obj.version_history.append(version)

        # Update content and compute new digest
        obj.content = new_content
        obj.version += 1
        obj.digest = self._compute_digest(obj)

        return obj

    def add_array_element(self, obj: UORObject, element: Any) -> UORObject:
        """Add element to mutable array object.

        Args:
            obj: UOR object (must be MUTABLE_ARRAY)
            element: Element to add

        Returns:
            Updated object

        Raises:
            ValueError: If object is not in MUTABLE_ARRAY mode
        """
        if obj.mode != ObjectMode.MUTABLE_ARRAY:
            raise ValueError(
                f"Cannot add element to object in mode {obj.mode}. "
                "Only MUTABLE_ARRAY mode supports dynamic elements."
            )

        obj.array_elements.append(element)
        obj.digest = self._compute_digest(obj)

        return obj

    def remove_array_element(self, obj: UORObject, index: int) -> UORObject:
        """Remove element from mutable array object.

        Args:
            obj: UOR object (must be MUTABLE_ARRAY)
            index: Index of element to remove

        Returns:
            Updated object

        Raises:
            ValueError: If object is not in MUTABLE_ARRAY mode or index invalid
        """
        if obj.mode != ObjectMode.MUTABLE_ARRAY:
            raise ValueError(
                f"Cannot remove element from object in mode {obj.mode}. "
                "Only MUTABLE_ARRAY mode supports dynamic elements."
            )

        if index < 0 or index >= len(obj.array_elements):
            raise ValueError(f"Invalid index {index} for array of length {len(obj.array_elements)}")

        obj.array_elements.pop(index)
        obj.digest = self._compute_digest(obj)

        return obj

    def get_array_elements(self, obj: UORObject) -> List[Any]:
        """Get elements from mutable array object.

        Args:
            obj: UOR object

        Returns:
            List of elements (empty if not in MUTABLE_ARRAY mode)
        """
        if obj.mode == ObjectMode.MUTABLE_ARRAY:
            return obj.array_elements
        return []

    def _compute_digest(self, obj: UORObject) -> str:
        """Compute digest for object using UOR canonicalization.

        Args:
            obj: UOR object

        Returns:
            UOR digest
        """
        content = obj.content
        if obj.mode == ObjectMode.MUTABLE_ARRAY:
            content = {
                "content": obj.content,
                "array_elements": obj.array_elements
            }

        return compute_uor_digest(content)
