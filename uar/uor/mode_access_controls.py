"""Mode-based access controls for UOR objects.

Enforces access control policies based on UOR object modes
(Immutable Singular, Mutable Singular, Mutable Array).
"""

import logging
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from .object_modes import ObjectMode, UORObject, ObjectModeEnforcer

logger = logging.getLogger(__name__)


class AccessAction(Enum):
    """Types of access actions on UOR objects."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    APPEND = "append"
    REMOVE = "remove"
    TRANSFORM = "transform"


@dataclass
class AccessRule:
    """Access rule for object mode and action."""

    mode: str
    allowed_actions: Set[AccessAction] = field(default_factory=set)
    denied_actions: Set[AccessAction] = field(default_factory=set)

    def allows(self, action: AccessAction) -> bool:
        """Check if action is allowed for this mode.

        Args:
            action: Access action to check

        Returns:
            True if action is allowed
        """
        if action in self.denied_actions:
            return False
        if action in self.allowed_actions:
            return True
        return False


@dataclass
class AccessDecision:
    """Result of access control decision."""

    allowed: bool
    action: AccessAction
    mode: str
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "allowed": self.allowed,
            "action": self.action.value,
            "mode": self.mode,
            "reason": self.reason,
        }


class ModeAccessController:
    """Access controller based on UOR object modes."""

    def __init__(self):
        """Initialize mode access controller."""
        self.mode_enforcer = ObjectModeEnforcer()
        self.rules: Dict[str, AccessRule] = {}
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default access rules for each mode."""
        # Immutable Singular: read-only
        self.rules[ObjectMode.IMMUTABLE_SINGULAR] = AccessRule(  # type: ignore
            mode=ObjectMode.IMMUTABLE_SINGULAR,  # type: ignore
            allowed_actions={AccessAction.READ},
            denied_actions={
                AccessAction.WRITE,
                AccessAction.DELETE,
                AccessAction.APPEND,
                AccessAction.REMOVE,
                AccessAction.TRANSFORM,
            },
        )

        # Mutable Singular: read and write
        self.rules[ObjectMode.MUTABLE_SINGULAR] = AccessRule(  # type: ignore
            mode=ObjectMode.MUTABLE_SINGULAR,  # type: ignore
            allowed_actions={
                AccessAction.READ,
                AccessAction.WRITE,
                AccessAction.TRANSFORM,
            },
            denied_actions={
                AccessAction.APPEND,
                AccessAction.REMOVE,
            },
        )

        # Mutable Array: read, write, append, remove
        self.rules[ObjectMode.MUTABLE_ARRAY] = AccessRule(  # type: ignore
            mode=ObjectMode.MUTABLE_ARRAY,
            allowed_actions={
                AccessAction.READ,
                AccessAction.WRITE,
                AccessAction.APPEND,
                AccessAction.REMOVE,
                AccessAction.TRANSFORM,
            },
            denied_actions=set(),
        )

    def check_access(
        self, obj: UORObject, action: AccessAction
    ) -> AccessDecision:
        """Check if action is allowed on object.

        Args:
            obj: UOR object to check access for
            action: Access action to check

        Returns:
            AccessDecision with result
        """
        rule = self.rules.get(obj.mode)

        if not rule:
            logger.warning("No access rule for mode: %s", obj.mode)
            return AccessDecision(
                allowed=False,
                action=action,
                mode=obj.mode,
                reason=f"No access rule for mode: {obj.mode}",
            )

        if rule.allows(action):
            return AccessDecision(
                allowed=True,
                action=action,
                mode=obj.mode,
            )
        else:
            return AccessDecision(
                allowed=False,
                action=action,
                mode=obj.mode,
                reason=(
                    f"Action {action.value} not allowed for mode {obj.mode}"
                ),
            )

    def enforce_access(self, obj: UORObject, action: AccessAction) -> bool:
        """Enforce access control on object.

        Args:
            obj: UOR object
            action: Access action

        Returns:
            True if access granted, raises PermissionError if denied

        Raises:
            PermissionError: If access is denied
        """
        decision = self.check_access(obj, action)

        if not decision.allowed:
            raise PermissionError(decision.reason or "Access denied")

        return True

    def add_rule(
        self, mode: str, allowed: Set[AccessAction], denied: Set[AccessAction]
    ) -> None:
        """Add custom access rule for a mode.

        Args:
            mode: Object mode
            allowed: Set of allowed actions
            denied: Set of denied actions
        """
        self.rules[mode] = AccessRule(  # type: ignore
            mode=mode,  # type: ignore
            allowed_actions=allowed,
            denied_actions=denied,
        )
        logger.info("Added custom rule for mode: %s", mode)

    def get_rule(self, mode: str) -> Optional[AccessRule]:
        """Get access rule for a mode.

        Args:
            mode: Object mode

        Returns:
            AccessRule if found, None otherwise
        """
        return self.rules.get(mode)  # type: ignore


class RoleBasedAccessController:
    """Role-based access control for UOR objects."""

    def __init__(self):
        """Initialize role-based access controller."""
        self.mode_controller = ModeAccessController()
        self.role_permissions: Dict[str, Set[AccessAction]] = {}
        self._setup_default_roles()

    def _setup_default_roles(self):
        """Setup default role permissions."""
        self.role_permissions = {
            "admin": {
                AccessAction.READ,
                AccessAction.WRITE,
                AccessAction.DELETE,
                AccessAction.APPEND,
                AccessAction.REMOVE,
                AccessAction.TRANSFORM,
            },
            "editor": {
                AccessAction.READ,
                AccessAction.WRITE,
                AccessAction.TRANSFORM,
            },
            "reader": {AccessAction.READ},
        }

    def check_access(
        self, obj: UORObject, action: AccessAction, role: str
    ) -> AccessDecision:
        """Check if action is allowed for role on object.

        Args:
            obj: UOR object
            action: Access action
            role: User role

        Returns:
            AccessDecision with result
        """
        # Check role permissions
        role_actions = self.role_permissions.get(role, set())

        if action not in role_actions:
            return AccessDecision(
                allowed=False,
                action=action,
                mode=obj.mode,
                reason=f"Role '{role}' does not have permission for {action.value}",  # noqa: E501
            )

        # Check mode-based access
        return self.mode_controller.check_access(obj, action)

    def add_role(self, role: str, permissions: Set[AccessAction]) -> None:
        """Add a custom role with permissions.

        Args:
            role: Role name
            permissions: Set of allowed actions
        """
        self.role_permissions[role] = permissions
        logger.info(
            "Added role: %s with permissions: %s", role, permissions
        )

    def get_role_permissions(self, role: str) -> Set[AccessAction]:
        """Get permissions for a role.

        Args:
            role: Role name

        Returns:
            Set of allowed actions
        """
        return self.role_permissions.get(role, set())
