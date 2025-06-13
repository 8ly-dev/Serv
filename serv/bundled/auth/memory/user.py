"""Memory-based user provider implementation."""

import time
from typing import Any, Dict, List, Optional, Set

from bevy import Container

from serv.auth.audit.enforcement import AuditJournal
from serv.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
)
from serv.auth.providers.user import UserProvider
from serv.auth.types import Permission, Role, User

from .store import MemoryStore


class MemoryUserProvider(UserProvider):
    """Memory-based user provider with role/permission management.
    
    This provider supports:
    - User creation, retrieval, and management
    - Role-based access control (RBAC)
    - Permission assignments and checking
    - User metadata and profile management
    - Thread-safe operations
    - Configurable user policies
    """
    
    def __init__(self, config: Dict[str, Any], container: Container):
        """Initialize memory user provider.
        
        Args:
            config: Provider configuration
            container: Dependency injection container
        """
        self.config = config
        self.container = container
        
        # Initialize memory store
        cleanup_interval = config.get("cleanup_interval", 300.0)
        self.store = MemoryStore(cleanup_interval=cleanup_interval)
        
        # User configuration
        self.default_roles = config.get("default_roles", [])
        self.require_email_verification = config.get("require_email_verification", False)
        self.allow_duplicate_emails = config.get("allow_duplicate_emails", False)
        self.auto_create_roles = config.get("auto_create_roles", True)
        
        # Initialize default roles and permissions if configured
        self._initialize_defaults()
        
        # Start cleanup task
        self._cleanup_started = False
    
    def _initialize_defaults(self) -> None:
        """Initialize default roles and permissions."""
        # Create default roles if they don't exist
        default_permissions = self.config.get("default_permissions", [])
        for perm_config in default_permissions:
            permission = Permission(
                name=perm_config["permission"],
                description=perm_config.get("description", ""),
                resource=perm_config.get("resource"),
                action=perm_config.get("action"),
            )
            self.store.set("permissions", permission.name, permission)
        
        # Create default roles
        default_role_configs = self.config.get("default_role_configs", [])
        for role_config in default_role_configs:
            # Convert permission names to Permission objects
            permission_objs = []
            for perm_name in role_config.get("permissions", []):
                permission = self.store.get("permissions", perm_name)
                if permission:
                    permission_objs.append(permission)
            
            role = Role(
                name=role_config["name"],
                description=role_config.get("description", ""),
                permissions=permission_objs,
            )
            self.store.set("roles", role.name, role)
    
    async def _ensure_cleanup_started(self) -> None:
        """Ensure cleanup task is started."""
        if not self._cleanup_started:
            await self.store.start_cleanup()
            self._cleanup_started = True
    
    async def create_user(
        self,
        username: str,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
        audit_journal: AuditJournal = None,
    ) -> User:
        """Create a new user."""
        await self._ensure_cleanup_started()
        
        user_id = username  # Use username as user ID for simplicity
        
        # Check if user already exists
        if self.store.exists("users", user_id):
            raise AuthenticationError(f"User {user_id} already exists")
        
        # Check email uniqueness if required
        if not self.allow_duplicate_emails:
            existing_user = await self.get_user_by_email(email)
            if existing_user:
                raise AuthenticationError(f"User with email {email} already exists")
        
        # Create user
        current_time = time.time()
        user = User(
            id=user_id,
            email=email,
            username=username,
            is_active=not self.require_email_verification,
            roles=list(self.default_roles),
            metadata={
                "created_at": current_time,
                "updated_at": current_time,
                "last_login": None,
                "login_count": 0,
                "is_verified": not self.require_email_verification,
                **(metadata or {}),
            }
        )
        
        # Store user
        self.store.set("users", user_id, user)
        
        # Index by email for lookups
        self.store.set("user_emails", email.lower(), user_id)
        
        # Index by username if provided
        if username:
            self.store.set("user_usernames", username.lower(), user_id)
        
        return user
    
    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        await self._ensure_cleanup_started()
        return self.store.get("users", user_id)
    
    
    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        await self._ensure_cleanup_started()
        
        user_id = self.store.get("user_emails", email.lower())
        if user_id:
            return self.store.get("users", user_id)
        return None
    
    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        await self._ensure_cleanup_started()
        
        user_id = self.store.get("user_usernames", username.lower())
        if user_id:
            return self.store.get("users", user_id)
        return None
    
    async def update_user(
        self, user_id: str, updates: dict[str, Any], audit_journal: AuditJournal
    ) -> User:
        """Update user information."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            raise AuthenticationError(f"User {user_id} not found")
        
        # Extract updates
        email = updates.get("email")
        username = updates.get("username")
        is_active = updates.get("is_active")
        metadata = updates.get("metadata")
        
        # Check email uniqueness if changing email
        if email and email != user.email and not self.allow_duplicate_emails:
            existing_user = await self.get_user_by_email(email)
            if existing_user and existing_user.id != user_id:
                raise AuthenticationError(f"User with email {email} already exists")
        
        # Update fields
        old_email = user.email
        old_username = user.username
        
        if email is not None:
            user.email = email
        if username is not None:
            user.username = username
        if is_active is not None:
            user.is_active = is_active
        if metadata is not None:
            user.metadata.update(metadata)
        
        user.metadata["updated_at"] = time.time()
        
        # Update indexes if email or username changed
        if email and email != old_email:
            self.store.delete("user_emails", old_email.lower())
            self.store.set("user_emails", email.lower(), user_id)
        
        if username and username != old_username:
            if old_username:
                self.store.delete("user_usernames", old_username.lower())
            self.store.set("user_usernames", username.lower(), user_id)
        
        # Store updated user
        self.store.set("users", user_id, user)
        
        return user
    
    async def delete_user(self, user_id: str, audit_journal: AuditJournal) -> None:
        """Delete a user."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            raise AuthenticationError(f"User {user_id} not found")
        
        # Remove from indexes
        if user.email:
            self.store.delete("user_emails", user.email.lower())
        if user.username:
            self.store.delete("user_usernames", user.username.lower())
        
        # Remove user
        self.store.delete("users", user_id)
    
    async def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign role to user."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            raise AuthenticationError(f"User {user_id} not found")
        
        # Check if role exists, create if auto_create_roles is enabled
        role = self.store.get("roles", role_name)
        if not role and self.auto_create_roles:
            role = Role(
                name=role_name,
                description=f"Auto-created role: {role_name}",
                permissions=[],
            )
            self.store.set("roles", role_name, role)
        elif not role:
            raise AuthorizationError(f"Role {role_name} does not exist")
        
        # Assign role
        if role_name not in user.roles:
            user.roles.append(role_name)
            user.metadata["updated_at"] = time.time()
            
            # Store updated user
            self.store.set("users", user_id, user)
    
    async def revoke_role(
        self,
        user_id: str,
        role_name: str,
        audit_journal: AuditJournal,
    ) -> bool:
        """Revoke role from user."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            return False
        
        if role_name in user.roles:
            user.roles.remove(role_name)
            user.metadata["updated_at"] = time.time()
            self.store.set("users", user_id, user)
            return True
        
        return False
    
    async def remove_role(self, user_id: str, role_name: str) -> None:
        """Remove a role from a user (interface method)."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            raise AuthenticationError(f"User {user_id} not found")
        
        if role_name in user.roles:
            user.roles.remove(role_name)
            user.metadata["updated_at"] = time.time()
            self.store.set("users", user_id, user)
    
    async def get_user_roles(self, user_id: str) -> set[Role]:
        """Get roles assigned to user."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            return set()
        
        roles = []
        for role_name in user.roles:
            role = self.store.get("roles", role_name)
            if role:
                roles.append(role)
        return set(roles) if roles else set()
    
    async def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get effective permissions for user."""
        await self._ensure_cleanup_started()
        
        user = self.store.get("users", user_id)
        if not user:
            return set()
        
        permissions = set()
        
        # Collect permissions from all user roles
        for role_name in user.roles:
            role = self.store.get("roles", role_name)
            if role:
                # Role.permissions is already a list of Permission objects
                for permission in role.permissions:
                    permissions.add(permission)
        
        return permissions
    
    async def has_permission(
        self,
        user_id: str,
        permission: str,
        resource: str | None = None,
    ) -> bool:
        """Check if user has specific permission."""
        user_permissions = await self.get_user_permissions(user_id)
        permission_names = {p.name for p in user_permissions}
        
        # Check exact permission match
        if permission in permission_names:
            return True
        
        # Check wildcard permissions
        permission_parts = permission.split(":")
        for i in range(len(permission_parts)):
            wildcard_perm = ":".join(permission_parts[:i+1]) + ":*"
            if wildcard_perm in permission_names:
                return True
        
        # Check for admin/superuser permissions
        if "admin:*" in permission_names or "*:*" in permission_names:
            return True
        
        return False
    
    async def has_role(self, user_id: str, role_name: str) -> bool:
        """Check if user has specific role."""
        user_roles = await self.get_user_roles(user_id)
        return role_name in user_roles
    
    async def create_role(
        self,
        name: str,
        description: str = "",
        permissions: Set[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        audit_journal: AuditJournal = None,
    ) -> Role:
        """Create a new role."""
        await self._ensure_cleanup_started()
        
        if self.store.exists("roles", name):
            raise AuthorizationError(f"Role {name} already exists")
        
        role = Role(
            name=name,
            description=description,
            permissions=permissions or set(),
            metadata={
                "created_at": time.time(),
                **(metadata or {}),
            }
        )
        
        self.store.set("roles", name, role)
        return role
    
    async def get_role(self, name: str) -> Role | None:
        """Get role by name."""
        await self._ensure_cleanup_started()
        return self.store.get("roles", name)
    
    async def update_role(
        self,
        name: str,
        description: str | None = None,
        permissions: Set[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        audit_journal: AuditJournal = None,
    ) -> Role | None:
        """Update role information."""
        await self._ensure_cleanup_started()
        
        role = self.store.get("roles", name)
        if not role:
            return None
        
        if description is not None:
            role.description = description
        if permissions is not None:
            role.permissions = permissions
        if metadata is not None:
            role.metadata.update(metadata)
        
        role.metadata["updated_at"] = time.time()
        self.store.set("roles", name, role)
        
        return role
    
    async def delete_role(
        self,
        name: str,
        audit_journal: AuditJournal,
    ) -> bool:
        """Delete a role."""
        await self._ensure_cleanup_started()
        
        if not self.store.exists("roles", name):
            return False
        
        # Remove role from all users
        for user in self.store.values("users"):
            if name in user.roles:
                user.roles.remove(name)
                user.metadata["updated_at"] = time.time()
                self.store.set("users", user.user_id, user)
        
        # Delete role
        self.store.delete("roles", name)
        return True
    
    async def create_permission(
        self,
        permission: str,
        description: str = "",
        resource: str | None = None,
        metadata: Dict[str, Any] | None = None,
        audit_journal: AuditJournal = None,
    ) -> Permission:
        """Create a new permission."""
        await self._ensure_cleanup_started()
        
        if self.store.exists("permissions", permission):
            raise AuthorizationError(f"Permission {permission} already exists")
        
        perm = Permission(
            name=permission,
            description=description,
            resource=resource,
            action=metadata.get("action") if metadata else None,
        )
        
        self.store.set("permissions", permission, perm)
        return perm
    
    async def get_permission(self, permission: str) -> Permission | None:
        """Get permission by name."""
        await self._ensure_cleanup_started()
        return self.store.get("permissions", permission)
    
    async def list_users(
        self, limit: int = 100, offset: int = 0, filters: dict[str, Any] | None = None
    ) -> list[User]:
        """List users with pagination."""
        await self._ensure_cleanup_started()
        
        users = []
        active_only = filters.get("active_only", False) if filters else False
        
        for user in self.store.values("users"):
            if active_only and not user.is_active:
                continue
            users.append(user)
        
        # Sort by creation time (newest first)
        users.sort(key=lambda u: u.metadata.get("created_at", 0), reverse=True)
        
        # Apply pagination
        return users[offset:offset + limit]
    
    async def list_roles(self) -> List[Role]:
        """List all roles."""
        await self._ensure_cleanup_started()
        
        roles = list(self.store.values("roles"))
        roles.sort(key=lambda r: r.name)
        return roles
    
    async def list_permissions(self) -> List[Permission]:
        """List all permissions."""
        await self._ensure_cleanup_started()
        
        permissions = list(self.store.values("permissions"))
        permissions.sort(key=lambda p: p.permission)
        return permissions
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get provider statistics."""
        await self._ensure_cleanup_started()
        
        total_users = self.store.size("users")
        active_users = len([u for u in self.store.values("users") if u.is_active])
        verified_users = len([u for u in self.store.values("users") if u.is_verified])
        total_roles = self.store.size("roles")
        total_permissions = self.store.size("permissions")
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,
            "total_roles": total_roles,
            "total_permissions": total_permissions,
            "default_roles": self.default_roles,
        }