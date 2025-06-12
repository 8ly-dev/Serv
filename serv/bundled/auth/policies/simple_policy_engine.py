"""
Simple policy engine implementation.

Provides basic rule-based authorization decisions using configurable
policies with support for roles, permissions, and custom rules.
"""

import fnmatch
from typing import Any

from serv.auth.policy_engine import PolicyEngine
from serv.auth.types import PolicyDecision


class SimplePolicyEngine(PolicyEngine):
    """Simple rule-based policy engine implementation."""

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate configuration for simple policy engine."""
        default_decision = config.get("default_decision", "deny")
        if default_decision not in ["allow", "deny"]:
            raise ValueError("default_decision must be 'allow' or 'deny'")

    def __init__(self, config: dict[str, Any]):
        """
        Initialize simple policy engine.

        Args:
            config: Configuration dictionary containing:
                - default_decision: Default decision when no policy matches ("allow" or "deny")
                - policies: List of policy rules
                - case_sensitive_permissions: Whether permission matching is case sensitive
        """
        super().__init__(config)

        self.default_decision = config.get("default_decision", "deny")
        self.policies = config.get("policies", [])
        self.case_sensitive_permissions = config.get("case_sensitive_permissions", True)

        # Validate default decision
        if self.default_decision not in ["allow", "deny"]:
            raise ValueError("default_decision must be 'allow' or 'deny'")

        # Validate and normalize policies
        self._validate_policies()

    def _validate_policies(self) -> None:
        """Validate policy configuration."""
        for i, policy in enumerate(self.policies):
            if not isinstance(policy, dict):
                raise ValueError(f"Policy {i} must be a dictionary")

            if "effect" not in policy:
                raise ValueError(f"Policy {i} missing required 'effect' field")

            if policy["effect"] not in ["allow", "deny"]:
                raise ValueError(f"Policy {i} effect must be 'allow' or 'deny'")

            # Ensure at least one condition is specified
            conditions = ["roles", "permissions", "resources", "users", "custom"]
            if not any(condition in policy for condition in conditions):
                raise ValueError(f"Policy {i} must specify at least one condition")

    async def evaluate(
        self, resource: str, action: str, user_context: dict[str, Any]
    ) -> PolicyDecision:
        """
        Evaluate authorization request against policies.

        Args:
            resource: Resource being accessed
            action: Action being performed
            user_context: User context with roles, permissions, etc.

        Returns:
            PolicyDecision with allow/deny and reasoning
        """
        user_id = user_context.get("user_id")
        user_roles = set(user_context.get("roles", []))
        user_permissions = set(user_context.get("permissions", []))

        # Normalize permissions for case-insensitive matching if configured
        if not self.case_sensitive_permissions:
            user_permissions = {perm.lower() for perm in user_permissions}

        # Evaluate each policy in order
        for i, policy in enumerate(self.policies):
            if await self._matches_policy(policy, resource, action, user_id, user_roles, user_permissions, user_context):
                effect = policy["effect"]
                reason = f"Policy {i + 1} matched: {policy.get('description', 'No description')}"

                return PolicyDecision(
                    allowed=(effect == "allow"),
                    reason=reason,
                    policy_id=str(i),
                    applied_policies=[policy],
                )

        # No policy matched, use default decision
        return PolicyDecision(
            allowed=(self.default_decision == "allow"),
            reason=f"No policy matched, using default decision: {self.default_decision}",
            policy_id="default",
            applied_policies=[],
        )

    async def _matches_policy(
        self,
        policy: dict[str, Any],
        resource: str,
        action: str,
        user_id: str | None,
        user_roles: set[str],
        user_permissions: set[str],
        user_context: dict[str, Any],
    ) -> bool:
        """Check if a policy matches the current request."""

        # Check user-specific rules
        if "users" in policy:
            policy_users = policy["users"]
            if isinstance(policy_users, str):
                policy_users = [policy_users]
            if user_id not in policy_users:
                return False

        # Check role-based rules
        if "roles" in policy:
            policy_roles = set(policy["roles"])
            if not policy_roles.intersection(user_roles):
                return False

        # Check permission-based rules
        if "permissions" in policy:
            policy_permissions = set(policy["permissions"])
            if not self.case_sensitive_permissions:
                policy_permissions = {perm.lower() for perm in policy_permissions}

            # Check if user has any of the required permissions
            if not policy_permissions.intersection(user_permissions):
                return False

        # Check resource-based rules
        if "resources" in policy:
            resource_patterns = policy["resources"]
            if isinstance(resource_patterns, str):
                resource_patterns = [resource_patterns]

            # Use glob patterns for resource matching
            if not any(fnmatch.fnmatch(resource, pattern) for pattern in resource_patterns):
                return False

        # Check action-based rules
        if "actions" in policy:
            action_patterns = policy["actions"]
            if isinstance(action_patterns, str):
                action_patterns = [action_patterns]

            # Use glob patterns for action matching
            if not any(fnmatch.fnmatch(action, pattern) for pattern in action_patterns):
                return False

        # Check custom rules (simple key-value matching)
        if "custom" in policy:
            custom_rules = policy["custom"]
            for key, expected_value in custom_rules.items():
                actual_value = user_context.get(key)
                if actual_value != expected_value:
                    return False

        # All conditions matched
        return True

    async def register_policy(self, policy: dict[str, Any]) -> str:
        """
        Register a new policy.

        Args:
            policy: Policy configuration dictionary

        Returns:
            Policy ID

        Raises:
            ValueError: If policy is invalid
        """
        # Validate policy structure
        if not isinstance(policy, dict):
            raise ValueError("Policy must be a dictionary")

        if "effect" not in policy:
            raise ValueError("Policy missing required 'effect' field")

        if policy["effect"] not in ["allow", "deny"]:
            raise ValueError("Policy effect must be 'allow' or 'deny'")

        # Add policy to the list
        self.policies.append(policy)
        policy_id = str(len(self.policies) - 1)

        return policy_id

    async def bulk_evaluate(
        self, requests: list[tuple[str, str, dict[str, Any]]]
    ) -> list[PolicyDecision]:
        """
        Evaluate multiple authorization requests efficiently.

        Args:
            requests: List of (resource, action, user_context) tuples

        Returns:
            List of PolicyDecision objects corresponding to each request
        """
        decisions = []

        for resource, action, user_context in requests:
            decision = await self.evaluate(resource, action, user_context)
            decisions.append(decision)

        return decisions

    async def get_user_permissions(self, user_context: dict[str, Any]) -> set[str]:
        """
        Get effective permissions for a user based on policies.

        Args:
            user_context: User context dictionary

        Returns:
            Set of permission strings the user effectively has
        """
        # Start with explicitly granted permissions
        explicit_permissions = set(user_context.get("permissions", []))

        # Add role-based permissions by checking which policies would allow access
        user_roles = set(user_context.get("roles", []))
        effective_permissions = explicit_permissions.copy()

        # For each policy that would allow access, extract the permissions it grants
        for policy in self.policies:
            if policy["effect"] == "allow" and "roles" in policy:
                policy_roles = set(policy["roles"])
                if policy_roles.intersection(user_roles):
                    # This policy applies to the user's roles
                    if "permissions" in policy:
                        effective_permissions.update(policy["permissions"])

        return effective_permissions

    async def _get_role_permissions(self, role: str) -> set[str]:
        """
        Get permissions for a specific role.

        Args:
            role: Role name

        Returns:
            Set of permissions for the role
        """
        permissions = set()
        
        # Look through policies to find permissions granted to this role
        for policy in self.policies:
            if policy["effect"] == "allow" and "roles" in policy:
                if role in policy["roles"]:
                    # This policy grants permissions to the role
                    if "permissions" in policy:
                        permissions.update(policy["permissions"])
        
        return permissions

    async def cleanup(self) -> None:
        """Clean up policy engine resources."""
        # No cleanup needed for simple in-memory implementation
        pass
