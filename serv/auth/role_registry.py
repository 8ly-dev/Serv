"""
RoleRegistry interface for the Serv authentication framework.

This module defines the abstract base class for role and permission management,
providing dynamic role definitions and permission assignments.

Security considerations:
- Role changes must trigger session invalidation
- Permission checks must be efficient and secure
- Role hierarchies must prevent privilege escalation
- Administrative actions must be audited
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .types import Permission, Role


class RoleRegistry(ABC):
    """
    Abstract base class for role and permission registries.

    Role registries manage the definition and assignment of roles and
    permissions throughout the authentication system. They provide
    dynamic role management with callback support for privilege changes.

    Security requirements:
    - Role definitions MUST be validated for security
    - Role changes MUST trigger appropriate callbacks
    - Permission checks MUST be efficient
    - Administrative actions MUST be audited
    - Role hierarchies MUST prevent privilege escalation

    All implementations should be stateless and use dependency injection
    for storage and notification services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the role registry.

        Args:
            config: Role registry configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)
        self._role_change_callbacks: list[Callable] = []

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate role registry configuration.

        Should validate role definitions, permission structures,
        and security settings.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid or insecure
        """
        pass

    @abstractmethod
    async def define_role(
        self,
        role_name: str,
        permissions: set[str],
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Role:
        """
        Define a new role with permissions.

        Creates or updates a role definition with the specified permissions.
        Role definitions should be immediately available for assignment.

        Security requirements:
        - MUST validate role name for security
        - MUST validate permissions exist
        - MUST prevent privilege escalation
        - SHOULD emit role definition audit event

        Args:
            role_name: Unique name for the role
            permissions: Set of permission names
            description: Human-readable role description
            metadata: Additional role metadata

        Returns:
            Created or updated Role object

        Raises:
            ValueError: If role definition is invalid or insecure

        Example:
            ```python
            async def define_role(
                self,
                role_name: str,
                permissions: Set[str],
                description: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None
            ) -> Role:
                # Validate role name
                if not self._is_valid_role_name(role_name):
                    raise ValueError(f"Invalid role name: {role_name}")

                # Validate permissions exist
                await self._validate_permissions_exist(permissions)

                # Check for privilege escalation
                if await self._would_escalate_privileges(role_name, permissions):
                    raise ValueError(f"Role would create privilege escalation: {role_name}")

                # Create role
                role = Role(
                    name=role_name,
                    permissions=permissions,
                    description=description,
                    metadata=metadata or {}
                )

                # Store role
                await self._store_role(role)

                # Emit audit event
                await self._emit_role_event("role_defined", role)

                return role
            ```
        """
        pass

    @abstractmethod
    async def assign_role(self, user_id: str, role_name: str) -> None:
        """
        Assign a role to a user.

        Assigns the specified role to the user. The assignment should
        be immediately effective for authorization checks.

        Security requirements:
        - MUST validate role exists
        - MUST validate user exists
        - MUST trigger role change callbacks
        - SHOULD emit role assignment audit event

        Args:
            user_id: User to assign role to
            role_name: Role to assign

        Raises:
            ValueError: If role or user doesn't exist

        Example:
            ```python
            async def assign_role(self, user_id: str, role_name: str) -> None:
                # Validate role exists
                role = await self._get_role(role_name)
                if not role:
                    raise ValueError(f"Role not found: {role_name}")

                # Validate user exists
                if not await self._user_exists(user_id):
                    raise ValueError(f"User not found: {user_id}")

                # Check if already assigned
                if await self._user_has_role(user_id, role_name):
                    return  # Already assigned

                # Assign role
                await self._store_user_role(user_id, role_name)

                # Trigger callbacks
                await self._trigger_role_change_callbacks(user_id, "assigned", role_name)

                # Emit audit event
                await self._emit_assignment_event("role_assigned", user_id, role_name)
            ```
        """
        pass

    @abstractmethod
    async def revoke_role(self, user_id: str, role_name: str) -> None:
        """
        Revoke a role from a user.

        Removes the specified role from the user. The revocation should
        be immediately effective for authorization checks.

        Security requirements:
        - MUST trigger role change callbacks
        - MUST be immediate and complete
        - SHOULD emit role revocation audit event

        Args:
            user_id: User to revoke role from
            role_name: Role to revoke

        Example:
            ```python
            async def revoke_role(self, user_id: str, role_name: str) -> None:
                # Check if user has role
                if not await self._user_has_role(user_id, role_name):
                    return  # Not assigned

                # Revoke role
                await self._remove_user_role(user_id, role_name)

                # Trigger callbacks
                await self._trigger_role_change_callbacks(user_id, "revoked", role_name)

                # Emit audit event
                await self._emit_assignment_event("role_revoked", user_id, role_name)
            ```
        """
        pass

    @abstractmethod
    async def check_permission(self, user_id: str, permission: str) -> bool:
        """
        Check if user has a specific permission.

        Checks whether the user has the specified permission through
        their assigned roles or direct permission grants.

        Security requirements:
        - MUST be efficient (< 5ms typical)
        - MUST check all user roles
        - MUST handle role hierarchies correctly
        - SHOULD cache results appropriately

        Args:
            user_id: User to check permission for
            permission: Permission to check

        Returns:
            True if user has permission, False otherwise

        Example:
            ```python
            async def check_permission(self, user_id: str, permission: str) -> bool:
                # Get user roles
                user_roles = await self._get_user_roles(user_id)

                # Check each role for permission
                for role_name in user_roles:
                    role = await self._get_role(role_name)
                    if role and role.has_permission(permission):
                        return True

                # Check direct permissions
                direct_permissions = await self._get_user_direct_permissions(user_id)
                return permission in direct_permissions
            ```
        """
        pass

    @abstractmethod
    async def get_user_roles(self, user_id: str) -> set[str]:
        """
        Get all roles assigned to a user.

        Args:
            user_id: User to get roles for

        Returns:
            Set of role names assigned to the user
        """
        pass

    @abstractmethod
    async def get_user_permissions(self, user_id: str) -> set[str]:
        """
        Get all permissions available to a user.

        Returns all permissions the user has through role assignments
        and direct permission grants.

        Args:
            user_id: User to get permissions for

        Returns:
            Set of permission names available to the user
        """
        pass

    @abstractmethod
    async def get_role(self, role_name: str) -> Role | None:
        """
        Get role definition by name.

        Args:
            role_name: Role name to look up

        Returns:
            Role object if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_roles(self) -> list[Role]:
        """
        List all defined roles.

        Returns:
            List of all Role objects
        """
        pass

    async def define_permission(
        self,
        permission_name: str,
        description: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Permission:
        """
        Define a new permission.

        Default implementation that can be overridden by providers
        that support dynamic permission definition.

        Args:
            permission_name: Unique permission name
            description: Human-readable description
            resource_type: Type of resource this permission applies to
            action: Action this permission allows
            metadata: Additional permission metadata

        Returns:
            Created Permission object
        """
        permission = Permission(
            name=permission_name,
            description=description,
            resource_type=resource_type,
            action=action,
            metadata=metadata or {},
        )

        # Default implementation just returns the permission
        # Providers should override to store it
        return permission

    def on_role_change(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Register callback for role changes.

        Callbacks are invoked when user role assignments change.
        Used to invalidate sessions, update caches, etc.

        Args:
            callback: Function called with (user_id, action, role_name)
                     where action is "assigned" or "revoked"
        """
        self._role_change_callbacks.append(callback)

    async def _trigger_role_change_callbacks(
        self, user_id: str, action: str, role_name: str
    ) -> None:
        """
        Trigger all registered role change callbacks.

        Args:
            user_id: User whose roles changed
            action: "assigned" or "revoked"
            role_name: Role that changed
        """
        for callback in self._role_change_callbacks:
            try:
                await callback(user_id, action, role_name)
            except Exception:
                # Log error but don't fail the role change
                # Providers should implement proper error handling
                pass

    def get_default_role(self) -> str | None:
        """
        Get the default role for new users.

        Returns:
            Default role name from configuration
        """
        return self.config.get("default_role")

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when role registry is being shut down.

        Override this method to cleanup any resources (connections,
        caches, etc.) when the role registry is being destroyed.
        """
        pass
