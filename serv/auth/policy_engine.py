"""
PolicyEngine interface for the Serv authentication framework.

This module defines the abstract base class for policy evaluation,
providing authorization decisions based on user context and requested actions.

Security considerations:
- Policy decisions must be deterministic and auditable
- Default policy should be denial (fail-secure)
- Policy evaluation must be efficient to prevent DoS
- Policy changes should invalidate relevant sessions
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .types import PolicyDecision


class PolicyEngine(ABC):
    """
    Abstract base class for policy evaluation engines.

    Policy engines evaluate authorization requests and return decisions
    about whether a user should be allowed to perform specific actions.
    They provide the core authorization logic while remaining flexible
    enough to support different policy models (RBAC, ABAC, etc.).

    Security requirements:
    - MUST default to denial (fail-secure)
    - MUST be deterministic for the same inputs
    - MUST provide clear reasoning for decisions
    - SHOULD be efficient to prevent DoS attacks
    - SHOULD support policy auditing and logging

    All implementations should be stateless and use dependency injection
    for any required services like role registries or external policy stores.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the policy engine.

        Args:
            config: Policy engine configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate policy engine configuration.

        Should validate policy configuration, default policies,
        and security settings.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def evaluate(
        self, user_context: dict[str, Any], action_descriptor: str
    ) -> PolicyDecision:
        """
        Evaluate authorization policy for a user action.

        Determines whether the user should be allowed to perform the
        specified action based on their context and the configured policies.

        Action descriptors follow the format: "resource_type:action"
        Examples: "post:read", "user:delete", "admin:access"

        Security requirements:
        - MUST default to denial for unknown actions
        - MUST validate all inputs
        - MUST return deterministic results
        - SHOULD include clear reasoning
        - SHOULD be efficient (< 10ms for simple policies)

        Args:
            user_context: User information including roles, permissions, attributes
            action_descriptor: Action being requested in "resource:action" format

        Returns:
            PolicyDecision with allow/deny and reasoning

        Example:
            ```python
            async def evaluate(
                self,
                user_context: Dict[str, Any],
                action_descriptor: str
            ) -> PolicyDecision:
                # Parse action descriptor
                try:
                    resource_type, action = action_descriptor.split(":", 1)
                except ValueError:
                    return PolicyDecision(
                        allowed=False,
                        reason="Invalid action descriptor format",
                        policy_name="format_validation"
                    )

                # Get user roles and permissions
                user_roles = set(user_context.get("roles", []))
                user_permissions = set(user_context.get("permissions", []))

                # Check direct permission
                required_permission = f"{resource_type}:{action}"
                if required_permission in user_permissions:
                    return PolicyDecision(
                        allowed=True,
                        reason=f"User has direct permission: {required_permission}",
                        policy_name="direct_permission"
                    )

                # Check role-based access
                if await self._check_role_access(user_roles, resource_type, action):
                    return PolicyDecision(
                        allowed=True,
                        reason=f"Access granted via role membership",
                        policy_name="role_based_access"
                    )

                # Default deny
                return PolicyDecision(
                    allowed=False,
                    reason=f"No permission for {action_descriptor}",
                    policy_name="default_deny"
                )
            ```
        """
        pass

    @abstractmethod
    async def register_policy(
        self,
        policy_name: str,
        policy_func: Callable[[dict[str, Any], str], PolicyDecision],
    ) -> None:
        """
        Register a custom policy function.

        Allows dynamic registration of policy evaluation functions.
        Used for extending the policy engine with custom business logic.

        Security requirements:
        - MUST validate policy function safety
        - SHOULD prevent policy conflicts
        - SHOULD support policy precedence

        Args:
            policy_name: Unique name for the policy
            policy_func: Function that evaluates the policy

        Raises:
            ValueError: If policy name conflicts or function is invalid

        Example:
            ```python
            async def register_policy(
                self,
                policy_name: str,
                policy_func: Callable[[Dict[str, Any], str], PolicyDecision]
            ) -> None:
                if policy_name in self._registered_policies:
                    raise ValueError(f"Policy already registered: {policy_name}")

                # Validate function signature
                if not callable(policy_func):
                    raise ValueError("Policy must be callable")

                # Store policy
                self._registered_policies[policy_name] = policy_func

                # Emit audit event
                await self._emit_policy_event("policy_registered", policy_name)
            ```
        """
        pass

    async def bulk_evaluate(
        self, user_context: dict[str, Any], action_descriptors: list[str]
    ) -> dict[str, PolicyDecision]:
        """
        Evaluate multiple actions in a single call.

        Default implementation that calls evaluate() for each action.
        Providers can override for more efficient batch processing.

        Args:
            user_context: User information
            action_descriptors: List of actions to evaluate

        Returns:
            Dictionary mapping action descriptors to decisions
        """
        results = {}
        for action in action_descriptors:
            results[action] = await self.evaluate(user_context, action)
        return results

    async def get_user_permissions(self, user_context: dict[str, Any]) -> set[str]:
        """
        Get all permissions available to a user.

        Default implementation returns permissions from user context.
        Providers can override to compute permissions dynamically.

        Args:
            user_context: User information

        Returns:
            Set of permission strings
        """
        permissions = set(user_context.get("permissions", []))

        # Add role-based permissions
        roles = user_context.get("roles", [])
        for role in roles:
            role_permissions = await self._get_role_permissions(role)
            permissions.update(role_permissions)

        return permissions

    async def _get_role_permissions(self, role: str) -> set[str]:
        """
        Get permissions for a specific role.

        Default implementation returns empty set.
        Providers should override to integrate with role registry.

        Args:
            role: Role name

        Returns:
            Set of permissions for the role
        """
        return set()

    def get_supported_actions(self) -> list[str]:
        """
        Get list of action descriptors supported by this policy engine.

        Returns:
            List of supported action descriptor patterns
        """
        return ["*:*"]  # Default supports all actions

    def is_action_supported(self, action_descriptor: str) -> bool:
        """
        Check if an action descriptor is supported.

        Args:
            action_descriptor: Action to check

        Returns:
            True if action is supported
        """
        try:
            resource_type, action = action_descriptor.split(":", 1)
            return bool(resource_type and action)
        except ValueError:
            return False

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when policy engine is being shut down.

        Override this method to cleanup any resources (connections,
        caches, etc.) when the policy engine is being destroyed.
        """
        pass
