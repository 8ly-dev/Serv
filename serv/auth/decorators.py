"""
Enhanced route decorators with authentication and authorization support.

This module extends the Serv route decorator system to support declarative
authentication and authorization requirements on route handlers.

Security considerations:
- Authentication requirements must be enforced before handler execution
- Authorization checks must be comprehensive and fail-secure
- Permission combinations must be validated for logical consistency
- Decorator metadata must be preserved for security auditing
"""

from collections.abc import Callable
from functools import wraps


class AuthRequirement:
    """
    Represents authentication/authorization requirements for a route.

    This class encapsulates all authentication and authorization metadata
    for a route handler, including required permissions, roles, and options.
    """

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
        Initialize authentication requirements.

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
        if self.require_permission:
            all_permissions.append(self.require_permission)
        all_permissions.extend(self.require_permissions)
        all_permissions.extend(self.require_any_permission)

        for permission in all_permissions:
            if not isinstance(permission, str) or not permission.strip():
                raise ValueError(f"Invalid permission name: {permission}")

        all_roles = []
        if self.require_role:
            all_roles.append(self.require_role)
        all_roles.extend(self.require_roles)

        for role in all_roles:
            if not isinstance(role, str) or not role.strip():
                raise ValueError(f"Invalid role name: {role}")

    def has_requirements(self) -> bool:
        """
        Check if this requirement specifies any authentication/authorization.

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

    def __eq__(self, other):
        """Check equality with another AuthRequirement."""
        if not isinstance(other, AuthRequirement):
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

    def __hash__(self):
        """Make AuthRequirement hashable for use in sets/dicts."""
        return hash(
            (
                self.require_auth,
                self.auth_optional,
                self.require_permission,
                tuple(self.require_permissions),
                tuple(self.require_any_permission),
                self.require_role,
                tuple(self.require_roles),
                self.allow_anonymous,
            )
        )


class AuthenticatedHandleDecorator:
    """
    Enhanced handle decorator with authentication and authorization support.

    This decorator extends the standard Serv handle decorator to support
    declarative authentication and authorization requirements.
    """

    def __init__(self, methods: set[str], auth_requirement: AuthRequirement):
        """
        Initialize the authenticated handle decorator.

        Args:
            methods: Set of HTTP methods this handler supports
            auth_requirement: Authentication/authorization requirements
        """
        self.methods = methods
        self.auth_requirement = auth_requirement

    def __call__(self, func: Callable) -> Callable:
        """
        Apply the decorator to a handler function.

        Args:
            func: Handler function to decorate

        Returns:
            Decorated handler function
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # The actual authentication/authorization checking will be handled
            # by middleware, but we preserve the function's behavior
            return await func(*args, **kwargs)

        # Store HTTP methods for routing system
        wrapper.__handle_methods__ = self.methods

        # Store authentication requirements for middleware to use
        wrapper.__auth_requirement__ = self.auth_requirement

        return wrapper

    def __or__(self, other):
        """Support for @handle.GET | handle.POST syntax"""
        if isinstance(other, AuthenticatedHandleDecorator):
            # Combine methods, but auth requirements must be identical
            if self.auth_requirement != other.auth_requirement:
                raise ValueError(
                    "Cannot combine handlers with different auth requirements"
                )

            return AuthenticatedHandleDecorator(
                self.methods | other.methods, self.auth_requirement
            )
        return NotImplemented


class AuthenticatedHandleRegistry:
    """
    Registry that provides authenticated method decorators.

    This registry extends the standard handle registry with authentication
    and authorization support.
    """

    def __init__(self):
        """Initialize the registry with standard HTTP method decorators."""
        # Standard decorators (no auth requirements)
        no_auth = AuthRequirement()

        self.GET = AuthenticatedHandleDecorator({"GET"}, no_auth)
        self.POST = AuthenticatedHandleDecorator({"POST"}, no_auth)
        self.PUT = AuthenticatedHandleDecorator({"PUT"}, no_auth)
        self.DELETE = AuthenticatedHandleDecorator({"DELETE"}, no_auth)
        self.PATCH = AuthenticatedHandleDecorator({"PATCH"}, no_auth)
        self.OPTIONS = AuthenticatedHandleDecorator({"OPTIONS"}, no_auth)
        self.HEAD = AuthenticatedHandleDecorator({"HEAD"}, no_auth)
        self.FORM = AuthenticatedHandleDecorator({"FORM"}, no_auth)

    def authenticated(
        self,
        methods: str | list[str] | set[str] = None,
        require_auth: bool = True,
        auth_optional: bool = False,
        require_permission: str | None = None,
        require_permissions: list[str] | None = None,
        require_any_permission: list[str] | None = None,
        require_role: str | None = None,
        require_roles: list[str] | None = None,
        allow_anonymous: bool = False,
    ):
        """
        Create a decorator with specific authentication requirements.

        Args:
            methods: HTTP methods to handle (defaults to GET)
            require_auth: Require user to be authenticated
            auth_optional: Authentication is optional
            require_permission: Single permission required
            require_permissions: All permissions required (AND logic)
            require_any_permission: Any permission required (OR logic)
            require_role: Single role required
            require_roles: Any role required (OR logic)
            allow_anonymous: Explicitly allow anonymous access

        Returns:
            AuthenticatedHandleDecorator with specified requirements

        Example:
            ```python
            class ProtectedRoute(Route):
                @handle.authenticated(
                    methods=["GET"],
                    require_permission="read_posts"
                )
                async def handle_get(self, request: GetRequest, session: Session = dependency()):
                    return f"Hello, {session.user_context['username']}"

                @handle.authenticated(
                    methods=["POST"],
                    require_permissions=["read_posts", "write_posts"]
                )
                async def handle_post(self, request: PostRequest):
                    return "Can read AND write posts"

                @handle.authenticated(
                    methods=["DELETE"],
                    require_any_permission=["admin", "moderator"]
                )
                async def handle_delete(self, request: DeleteRequest):
                    return "Has admin OR moderator permission"
            ```
        """
        # Normalize methods
        if methods is None:
            method_set = {"GET"}
        elif isinstance(methods, str):
            method_set = {methods.upper()}
        elif isinstance(methods, list | set):
            method_set = {m.upper() for m in methods}
        else:
            raise ValueError("Methods must be string, list, or set")

        # Create auth requirement
        auth_requirement = AuthRequirement(
            require_auth=require_auth,
            auth_optional=auth_optional,
            require_permission=require_permission,
            require_permissions=require_permissions,
            require_any_permission=require_any_permission,
            require_role=require_role,
            require_roles=require_roles,
            allow_anonymous=allow_anonymous,
        )

        return AuthenticatedHandleDecorator(method_set, auth_requirement)

    def with_permission(
        self, permission: str, methods: str | list[str] | set[str] = None
    ):
        """
        Create a decorator requiring a specific permission.

        Args:
            permission: Permission name required
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator requiring the permission
        """
        return self.authenticated(methods=methods, require_permission=permission)

    def with_permissions(
        self, permissions: list[str], methods: str | list[str] | set[str] = None
    ):
        """
        Create a decorator requiring all specified permissions.

        Args:
            permissions: List of permissions all required (AND logic)
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator requiring all permissions
        """
        return self.authenticated(methods=methods, require_permissions=permissions)

    def with_any_permission(
        self, permissions: list[str], methods: str | list[str] | set[str] = None
    ):
        """
        Create a decorator requiring any of the specified permissions.

        Args:
            permissions: List of permissions where any is sufficient (OR logic)
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator requiring any permission
        """
        return self.authenticated(methods=methods, require_any_permission=permissions)

    def with_role(self, role: str, methods: str | list[str] | set[str] = None):
        """
        Create a decorator requiring a specific role.

        Args:
            role: Role name required
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator requiring the role
        """
        return self.authenticated(methods=methods, require_role=role)

    def with_roles(self, roles: list[str], methods: str | list[str] | set[str] = None):
        """
        Create a decorator requiring any of the specified roles.

        Args:
            roles: List of roles where any is sufficient
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator requiring any role
        """
        return self.authenticated(methods=methods, require_roles=roles)

    def optional_auth(self, methods: str | list[str] | set[str] = None):
        """
        Create a decorator with optional authentication.

        Handler will receive user context if available, but doesn't require it.

        Args:
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator with optional authentication
        """
        return self.authenticated(
            methods=methods, auth_optional=True, require_auth=False
        )

    def anonymous_only(self, methods: str | list[str] | set[str] = None):
        """
        Create a decorator that explicitly allows only anonymous access.

        Useful for login/registration endpoints that should not be
        accessible to already-authenticated users.

        Args:
            methods: HTTP methods to handle

        Returns:
            AuthenticatedHandleDecorator allowing only anonymous access
        """
        return self.authenticated(
            methods=methods, allow_anonymous=True, require_auth=False
        )


# Create the enhanced handle instance
# This replaces the standard handle registry when auth is enabled
auth_handle = AuthenticatedHandleRegistry()
