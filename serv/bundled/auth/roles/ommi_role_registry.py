"""
Ommi-based role registry implementation.

Provides database-backed role and permission management using Ommi
for efficient queries and relationship handling.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from bevy import Inject, auto_inject, injectable

from serv.auth.role_registry import RoleRegistry
from serv.auth.types import Permission, Role
from serv.database import DatabaseManager


class OmmiRoleRegistry(RoleRegistry):
    """Ommi-based role registry implementation."""

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate configuration for Ommi role registry."""
        # No required config for basic implementation
        pass

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Ommi role registry.

        Args:
            config: Configuration dictionary containing:
                - database_qualifier: Database qualifier for Ommi (default: "auth")
                - cache_expiry: Cache expiry time in seconds (default: 300)
                - case_sensitive: Whether role/permission names are case sensitive
        """
        super().__init__(config)

        self.database_qualifier = config.get("database_qualifier", "auth")
        self.cache_expiry = config.get("cache_expiry", 300)  # 5 minutes
        self.case_sensitive = config.get("case_sensitive", True)

        # Simple in-memory cache for frequently accessed data
        self._role_cache = {}
        self._permission_cache = {}
        self._user_roles_cache = {}
        self._last_cache_update = {}

    def _normalize_name(self, name: str) -> str:
        """Normalize role/permission name based on case sensitivity setting."""
        return name if self.case_sensitive else name.lower()

    async def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._last_cache_update:
            return False

        last_update = self._last_cache_update[cache_key]
        elapsed = (datetime.now(UTC) - last_update).total_seconds()
        return elapsed < self.cache_expiry

    @auto_inject
    @injectable
    async def define_role(
        self, name: str, description: str = "", permissions: list[str] | None = None, database: Inject[DatabaseManager] = None
    ) -> Role:
        """
        Define a new role with optional permissions.

        Args:
            name: Role name
            description: Role description
            permissions: List of permission names to grant to this role
            database: Database service injected via DI

        Returns:
            Created Role object

        Raises:
            ValueError: If role already exists or validation fails
            RuntimeError: If database operation fails
        """
        try:
            from ..models import RoleModel, RolePermissionModel

            normalized_name = self._normalize_name(name)

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Check if role already exists
            existing_result = await ommi_instance.find(RoleModel.name == normalized_name).one()
            if existing_result.is_success():
                raise ValueError(f"Role '{name}' already exists")

            # Create new role
            role_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()

            role_model = RoleModel(
                role_id=role_id,
                name=normalized_name,
                description=description,
                created_at=now,
                updated_at=now,
                is_active=True,
                metadata="{}",
            )

            # Save role
            role_result = await ommi_instance.add(role_model)
            saved_roles = await role_result.or_raise()
            saved_role = saved_roles[0]

            # Add permissions if specified
            role_permissions = []
            if permissions:
                for permission_name in permissions:
                    # Ensure permission exists
                    await self._ensure_permission_exists(permission_name, database)

                    # Create role-permission relationship
                    role_perm_model = RolePermissionModel(
                        role_id=role_id,
                        permission_name=self._normalize_name(permission_name),
                        granted_at=now,
                        granted_by="system",
                    )

                    perm_result = await ommi_instance.add(role_perm_model)
                    await perm_result.or_raise()
                    role_permissions.append(permission_name)

            # Clear cache
            self._role_cache.clear()
            self._last_cache_update.clear()

            return Role(
                role_id=role_id,
                name=name,  # Return original case
                description=description,
                permissions=role_permissions,
                metadata={},
                created_at=datetime.fromisoformat(saved_role.created_at),
                is_active=True,
            )

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to define role: {e}") from e

    @auto_inject
    @injectable
    async def define_permission(
        self, name: str, description: str = "", resource: str | None = None, database: Inject[DatabaseManager] = None
    ) -> Permission:
        """
        Define a new permission.

        Args:
            name: Permission name
            description: Permission description
            resource: Resource this permission applies to
            database: Database service injected via DI

        Returns:
            Created Permission object

        Raises:
            ValueError: If permission already exists
            RuntimeError: If database operation fails
        """
        try:
            from ..models import PermissionModel

            normalized_name = self._normalize_name(name)

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Check if permission already exists
            existing_result = await ommi_instance.find(PermissionModel.name == normalized_name).one()
            if existing_result.is_success():
                raise ValueError(f"Permission '{name}' already exists")

            # Create new permission
            permission_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()

            permission_model = PermissionModel(
                permission_id=permission_id,
                name=normalized_name,
                description=description,
                resource=resource,
                created_at=now,
                is_active=True,
            )

            # Save permission
            result = await ommi_instance.add(permission_model)
            saved_permissions = await result.or_raise()
            saved_permission = saved_permissions[0]

            # Clear cache
            self._permission_cache.clear()
            self._last_cache_update.clear()

            return Permission(
                permission_id=permission_id,
                name=name,  # Return original case
                description=description,
                resource=resource,
                created_at=datetime.fromisoformat(saved_permission.created_at),
                is_active=True,
            )

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to define permission: {e}") from e

    @auto_inject
    @injectable
    async def assign_role(self, user_id: str, role_name: str, database: Inject[DatabaseManager] = None) -> bool:
        """
        Assign a role to a user.

        Args:
            user_id: User ID
            role_name: Role name to assign
            database: Database service injected via DI

        Returns:
            True if assignment succeeded

        Raises:
            ValueError: If role doesn't exist
            RuntimeError: If database operation fails
        """
        try:
            from ..models import RoleModel, UserRoleModel

            normalized_role = self._normalize_name(role_name)

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Verify role exists
            role_result = await ommi_instance.find(RoleModel.name == normalized_role).one()
            role = await role_result.or_raise()

            # Check if assignment already exists
            existing_result = await ommi_instance.find(
                UserRoleModel.user_id == user_id, UserRoleModel.role_id == role.role_id
            ).one()

            if existing_result.is_success():
                return True  # Already assigned

            # Create assignment
            assignment = UserRoleModel(
                user_id=user_id,
                role_id=role.role_id,
                assigned_at=datetime.now(UTC).isoformat(),
                assigned_by="system",
            )

            result = await ommi_instance.add(assignment)
            await result.or_raise()

            # Clear user cache
            if user_id in self._user_roles_cache:
                del self._user_roles_cache[user_id]

            return True

        except Exception as e:
            if "or_raise" in str(e):
                raise ValueError(f"Role '{role_name}' not found") from e
            raise RuntimeError(f"Failed to assign role: {e}") from e

    @auto_inject
    @injectable
    async def revoke_role(self, user_id: str, role_name: str, database: Inject[DatabaseManager] = None) -> bool:
        """
        Revoke a role from a user.

        Args:
            user_id: User ID
            role_name: Role name to revoke
            database: Database service injected via DI

        Returns:
            True if revocation succeeded

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            from ..models import RoleModel, UserRoleModel

            normalized_role = self._normalize_name(role_name)

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Get role ID
            role_result = await ommi_instance.find(RoleModel.name == normalized_role).one()
            if not role_result.is_success():
                return True  # Role doesn't exist, nothing to revoke

            role = await role_result.or_raise()

            # Delete assignment
            delete_result = await ommi_instance.find(
                UserRoleModel.user_id == user_id, UserRoleModel.role_id == role.role_id
            ).delete()

            await delete_result.or_raise()

            # Clear user cache
            if user_id in self._user_roles_cache:
                del self._user_roles_cache[user_id]

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to revoke role: {e}") from e

    @auto_inject
    @injectable
    async def check_permission(
        self, user_id: str, permission_name: str, database: Inject[DatabaseManager] = None
    ) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User ID
            permission_name: Permission name to check
            database: Database service injected via DI

        Returns:
            True if user has the permission

        Raises:
            RuntimeError: If database operation fails
        """
        user_permissions = await self.get_user_permissions(user_id, database)
        normalized_permission = self._normalize_name(permission_name)
        return any(self._normalize_name(perm) == normalized_permission for perm in user_permissions)

    @auto_inject
    @injectable
    async def get_user_roles(self, user_id: str, database: Inject[DatabaseManager] = None) -> list[str]:
        """
        Get all roles assigned to a user.

        Args:
            user_id: User ID
            database: Database service injected via DI

        Returns:
            List of role names

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            # Check cache first
            if await self._is_cache_valid(f"user_roles_{user_id}"):
                return self._user_roles_cache.get(user_id, [])

            from ..models import RoleModel, UserRoleModel

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Query user roles with join
            user_role_result = await ommi_instance.find(UserRoleModel.user_id == user_id).all()
            user_roles = await user_role_result.or_raise()

            role_names = []
            async for user_role in user_roles:
                # Get role details
                role_result = await ommi_instance.find(RoleModel.role_id == user_role.role_id).one()
                if role_result.is_success():
                    role = await role_result.or_raise()
                    role_names.append(role.name)

            # Cache result
            self._user_roles_cache[user_id] = role_names
            self._last_cache_update[f"user_roles_{user_id}"] = datetime.now(UTC)

            return role_names

        except Exception as e:
            raise RuntimeError(f"Failed to get user roles: {e}") from e

    @auto_inject
    @injectable
    async def get_user_permissions(self, user_id: str, database: Inject[DatabaseManager] = None) -> list[str]:
        """
        Get all permissions granted to a user through their roles.

        Args:
            user_id: User ID
            database: Database service injected via DI

        Returns:
            List of permission names

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            # Check cache first
            cache_key = f"user_permissions_{user_id}"
            if await self._is_cache_valid(cache_key):
                return self._user_roles_cache.get(cache_key, [])

            from ..models import RoleModel, RolePermissionModel

            if database is None:
                raise RuntimeError("Database service not available for role registry")

            ommi_instance = await database.get_connection(self.database_qualifier)

            # Get user's roles
            user_roles = await self.get_user_roles(user_id, database)
            if not user_roles:
                return []

            # Get all permissions for these roles
            permissions = set()

            for role_name in user_roles:
                # Get role ID
                role_result = await ommi_instance.find(RoleModel.name == self._normalize_name(role_name)).one()
                if role_result.is_success():
                    role = await role_result.or_raise()

                    # Get role permissions
                    perm_result = await ommi_instance.find(RolePermissionModel.role_id == role.role_id).all()
                    role_permissions = await perm_result.or_raise()

                    async for role_perm in role_permissions:
                        permissions.add(role_perm.permission_name)

            permission_list = list(permissions)

            # Cache result
            self._user_roles_cache[cache_key] = permission_list
            self._last_cache_update[cache_key] = datetime.now(UTC)

            return permission_list

        except Exception as e:
            raise RuntimeError(f"Failed to get user permissions: {e}") from e

    async def _ensure_permission_exists(self, permission_name: str, database: DatabaseManager) -> None:
        """Ensure a permission exists, creating it if necessary."""
        try:
            await self.define_permission(permission_name, f"Auto-created permission: {permission_name}", database=database)
        except ValueError:
            # Permission already exists, which is fine
            pass

    async def cleanup(self) -> None:
        """Clean up role registry resources."""
        # Clear in-memory caches
        self._role_cache.clear()
        self._permission_cache.clear()
        self._user_roles_cache.clear()
        self._last_cache_update.clear()
