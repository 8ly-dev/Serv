"""
Declarative authentication and authorization rule processing.

This module handles parsing and evaluation of auth rules from extension.yaml
configuration, providing integration between the extension system and auth middleware.
"""

from typing import Any


class AuthRule:
    """Represents parsed authentication and authorization requirements."""

    def __init__(
        self,
        require_auth: bool = False,
        auth_optional: bool = False,
        require_permission: str | None = None,
        require_permissions: list[str] | None = None,
        require_any_permission: list[str] | None = None,
        require_role: str | None = None,
        require_roles: list[str] | None = None,
        allow_anonymous: bool = False,
    ):
        """
        Initialize authentication rule.

        Args:
            require_auth: Require user to be authenticated
            auth_optional: Authentication is optional (user context if available)
            require_permission: Single permission required
            require_permissions: All permissions in list required (AND logic)
            require_any_permission: Any permission in list required (OR logic)
            require_role: Single role required
            require_roles: Any role in list required (OR logic)
            allow_anonymous: Explicitly allow anonymous access
        """
        self.require_auth = require_auth
        self.auth_optional = auth_optional
        self.require_permission = require_permission
        self.require_permissions = require_permissions or []
        self.require_any_permission = require_any_permission or []
        self.require_role = require_role
        self.require_roles = require_roles or []
        self.allow_anonymous = allow_anonymous

        # Validate configuration
        self._validate_requirements()

    def _validate_requirements(self):
        """
        Validate that authentication requirements are logically consistent.

        Raises:
            ValueError: If requirements are contradictory or invalid
        """
        # Check for contradictory settings
        if self.require_auth and self.allow_anonymous:
            raise ValueError(
                "Cannot both require authentication and allow anonymous access"
            )

        if self.auth_optional and self.require_auth:
            raise ValueError("Cannot both require authentication and make it optional")

        # If any auth requirements are specified, auth should be required
        has_auth_requirements = any(
            [
                self.require_permission,
                self.require_permissions,
                self.require_any_permission,
                self.require_role,
                self.require_roles,
            ]
        )

        if has_auth_requirements and not self.require_auth and not self.auth_optional:
            # Automatically enable required auth if permissions/roles are specified
            self.require_auth = True

        # Validate permission/role names
        all_permissions = []
        if self.require_permission is not None:
            all_permissions.append(self.require_permission)
        all_permissions.extend(self.require_permissions)
        all_permissions.extend(self.require_any_permission)

        for permission in all_permissions:
            if not isinstance(permission, str) or not permission.strip():
                raise ValueError(f"Invalid permission name: {permission}")

        all_roles = []
        if self.require_role is not None:
            all_roles.append(self.require_role)
        all_roles.extend(self.require_roles)

        for role in all_roles:
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"Invalid role name: {role}")

    def has_requirements(self) -> bool:
        """
        Check if this rule specifies any authentication/authorization.

        Returns:
            True if any requirements are specified
        """
        return any(
            [
                self.require_auth,
                self.auth_optional,
                self.require_permission,
                self.require_permissions,
                self.require_any_permission,
                self.require_role,
                self.require_roles,
                self.allow_anonymous,
            ]
        )

    def requires_authentication(self) -> bool:
        """
        Check if authentication is required (not optional).

        Returns:
            True if authentication is required
        """
        return self.require_auth and not self.auth_optional

    def get_all_required_permissions(self) -> set[str]:
        """
        Get all permissions that are individually required.

        Returns:
            Set of permission names that must all be present
        """
        permissions = set()

        if self.require_permission:
            permissions.add(self.require_permission)

        permissions.update(self.require_permissions)

        return permissions

    def get_any_required_permissions(self) -> set[str]:
        """
        Get permissions where any one is sufficient.

        Returns:
            Set of permission names where any one is sufficient
        """
        return set(self.require_any_permission)

    def get_required_roles(self) -> set[str]:
        """
        Get all required roles.

        Returns:
            Set of role names where any one is sufficient
        """
        roles = set()

        if self.require_role:
            roles.add(self.require_role)

        roles.update(self.require_roles)

        return roles

    def evaluate_permissions(self, user_permissions: set[str]) -> bool:
        """
        Evaluate if user permissions satisfy the rule requirements.

        Args:
            user_permissions: Set of permissions the user has

        Returns:
            True if permission requirements are satisfied
        """
        # Check all required permissions (AND logic)
        all_required = self.get_all_required_permissions()
        if all_required and not all_required.issubset(user_permissions):
            return False

        # Check any required permissions (OR logic)
        any_required = self.get_any_required_permissions()
        if any_required and not any_required.intersection(user_permissions):
            return False

        return True

    def evaluate_roles(self, user_roles: set[str]) -> bool:
        """
        Evaluate if user roles satisfy the rule requirements.

        Args:
            user_roles: Set of roles the user has

        Returns:
            True if role requirements are satisfied
        """
        required_roles = self.get_required_roles()
        if required_roles and not required_roles.intersection(user_roles):
            return False

        return True

    def merge_with(self, other: "AuthRule") -> "AuthRule":
        """
        Merge this auth rule with another, creating a new rule with combined requirements.

        Router-level rules are merged with route-level rules, with route-level taking precedence
        for specific settings while combining requirement lists.

        Args:
            other: Another auth rule to merge with (takes precedence)

        Returns:
            New AuthRule with merged requirements
        """
        # Combine permissions and roles from both rules
        combined_permissions = list(
            self.require_permissions + other.require_permissions
        )
        if self.require_permission:
            combined_permissions.append(self.require_permission)
        if other.require_permission:
            combined_permissions.append(other.require_permission)

        combined_roles = list(self.require_roles + other.require_roles)
        if self.require_role:
            combined_roles.append(self.require_role)
        if other.require_role:
            combined_roles.append(other.require_role)

        # Route-level auth settings take precedence for boolean flags
        return AuthRule(
            require_auth=other.require_auth or self.require_auth,
            auth_optional=other.auth_optional
            if hasattr(other, "auth_optional") and other.auth_optional is not None
            else self.auth_optional,
            require_permission=None,  # Combined into require_permissions
            require_permissions=list(set(combined_permissions)),
            require_any_permission=list(
                set(self.require_any_permission + other.require_any_permission)
            ),
            require_role=None,  # Combined into require_roles
            require_roles=list(set(combined_roles)),
            allow_anonymous=other.allow_anonymous
            if hasattr(other, "allow_anonymous") and other.allow_anonymous is not None
            else self.allow_anonymous,
        )

    def __eq__(self, other) -> bool:
        """Check equality with another AuthRule."""
        if not isinstance(other, AuthRule):
            return False

        return (
            self.require_auth == other.require_auth
            and self.auth_optional == other.auth_optional
            and self.require_permission == other.require_permission
            and self.require_permissions == other.require_permissions
            and self.require_any_permission == other.require_any_permission
            and self.require_role == other.require_role
            and self.require_roles == other.require_roles
            and self.allow_anonymous == other.allow_anonymous
        )


class DeclarativeAuthProcessor:
    """Processes declarative auth configuration from extension.yaml."""

    @staticmethod
    def validate_auth_config(auth_config: dict[str, Any]) -> None:
        """
        Validate auth configuration for common errors.

        Args:
            auth_config: Auth configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(auth_config, dict):
            raise ValueError("Auth configuration must be a dictionary")

        # Check for unknown keys
        valid_keys = {
            "require_auth",
            "auth_optional",
            "require_permission",
            "require_permissions",
            "require_any_permission",
            "require_role",
            "require_roles",
            "allow_anonymous",
        }
        unknown_keys = set(auth_config.keys()) - valid_keys
        if unknown_keys:
            raise ValueError(
                f"Unknown auth configuration keys: {', '.join(unknown_keys)}"
            )

        # Validate permission lists
        for key in ["require_permissions", "require_any_permission"]:
            if key in auth_config:
                value = auth_config[key]
                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a list")
                if not all(isinstance(p, str) for p in value):
                    raise ValueError(f"All items in {key} must be strings")

        # Validate role lists
        for key in ["require_roles"]:
            if key in auth_config:
                value = auth_config[key]
                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a list")
                if not all(isinstance(r, str) for r in value):
                    raise ValueError(f"All items in {key} must be strings")

        # Validate single permission/role strings
        for key in ["require_permission", "require_role"]:
            if key in auth_config:
                value = auth_config[key]
                if not isinstance(value, str):
                    raise ValueError(f"{key} must be a string")

        # Validate boolean fields
        for key in ["require_auth", "auth_optional", "allow_anonymous"]:
            if key in auth_config:
                value = auth_config[key]
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be a boolean")

    @staticmethod
    def parse_auth_config(auth_config: dict[str, Any] | None) -> AuthRule | None:
        """
        Parse auth configuration from extension.yaml into an AuthRule.

        Args:
            auth_config: Auth configuration dictionary from extension.yaml

        Returns:
            AuthRule instance or None if no auth config
        """
        if not auth_config:
            return None

        # Validate configuration before parsing
        DeclarativeAuthProcessor.validate_auth_config(auth_config)

        return AuthRule(
            require_auth=auth_config.get("require_auth", False),
            auth_optional=auth_config.get("auth_optional", False),
            require_permission=auth_config.get("require_permission"),
            require_permissions=auth_config.get("require_permissions", []),
            require_any_permission=auth_config.get("require_any_permission", []),
            require_role=auth_config.get("require_role"),
            require_roles=auth_config.get("require_roles", []),
            allow_anonymous=auth_config.get("allow_anonymous", False),
        )

    @staticmethod
    def merge_router_and_route_auth(
        router_auth: AuthRule | None, route_auth: AuthRule | None
    ) -> AuthRule | None:
        """
        Merge router-level and route-level auth rules.

        Args:
            router_auth: Router-level auth rule
            route_auth: Route-level auth rule

        Returns:
            Merged auth rule or None if no auth requirements
        """
        if not router_auth and not route_auth:
            return None

        if not router_auth:
            return route_auth

        if not route_auth:
            return router_auth

        return router_auth.merge_with(route_auth)

    @staticmethod
    def evaluate_auth_rule(
        auth_rule: AuthRule,
        user_context: dict[str, Any] | None,
    ) -> tuple[bool, str]:
        """
        Evaluate an auth rule against user context.

        Args:
            auth_rule: Auth rule to evaluate
            user_context: User context from authentication

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if anonymous access is explicitly allowed
        if auth_rule.allow_anonymous and not user_context:
            return True, "Anonymous access allowed"

        # Check if authentication is required
        if auth_rule.requires_authentication() and not user_context:
            return False, "Authentication required"

        # If auth is optional and no user context, allow
        if auth_rule.auth_optional and not user_context:
            return True, "Optional authentication - no user"

        # If we have user context, evaluate permissions and roles
        if user_context:
            user_permissions = set(user_context.get("permissions", []))
            user_roles = set(user_context.get("roles", []))

            # Evaluate permissions
            if not auth_rule.evaluate_permissions(user_permissions):
                required_perms = auth_rule.get_all_required_permissions()
                any_perms = auth_rule.get_any_required_permissions()
                if required_perms:
                    missing = required_perms - user_permissions
                    return False, f"Missing required permissions: {', '.join(missing)}"
                if any_perms:
                    return False, f"Requires any of permissions: {', '.join(any_perms)}"

            # Evaluate roles
            if not auth_rule.evaluate_roles(user_roles):
                required_roles = auth_rule.get_required_roles()
                return False, f"Requires any of roles: {', '.join(required_roles)}"

            return True, "Authorization successful"

        # Default allow if no specific requirements
        if not auth_rule.has_requirements():
            return True, "No authentication requirements"

        return False, "Authentication failed"
