"""User provider interface."""

from abc import abstractmethod
from typing import Any

from ..audit.enforcement import AuditEmitter, AuditRequired
from ..audit.events import AuditEventType
from ..types import Permission, Role, User
from .base import BaseProvider


class UserProvider(BaseProvider):
    """Abstract base class for user management."""

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: ID of the user

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username to search for

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: Email to search for

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.USER_CREATE)
    async def create_user(
        self,
        username: str,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
        audit_emitter: AuditEmitter = None
    ) -> User:
        """Create a new user.

        Args:
            username: Username for the new user
            email: Email for the new user
            metadata: Additional user metadata
            audit_emitter: Audit emitter for tracking events

        Returns:
            Created user
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.USER_UPDATE)
    async def update_user(
        self,
        user_id: str,
        updates: dict[str, Any],
        audit_emitter: AuditEmitter
    ) -> User:
        """Update user information.

        Args:
            user_id: ID of the user to update
            updates: Dictionary of fields to update
            audit_emitter: Audit emitter for tracking events

        Returns:
            Updated user
        """
        pass

    @abstractmethod
    @AuditRequired(AuditEventType.USER_DELETE)
    async def delete_user(
        self,
        user_id: str,
        audit_emitter: AuditEmitter
    ) -> None:
        """Delete a user.

        Args:
            user_id: ID of the user to delete
            audit_emitter: Audit emitter for tracking events
        """
        pass

    @abstractmethod
    async def list_users(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> list[User]:
        """List users with pagination and filtering.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            filters: Optional filters to apply

        Returns:
            List of users matching criteria
        """
        pass

    @abstractmethod
    async def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all permissions for a user.

        Args:
            user_id: ID of the user

        Returns:
            Set of permissions for the user
        """
        pass

    @abstractmethod
    async def get_user_roles(self, user_id: str) -> set[Role]:
        """Get all roles for a user.

        Args:
            user_id: ID of the user

        Returns:
            Set of roles for the user
        """
        pass

    @abstractmethod
    async def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user.

        Args:
            user_id: ID of the user
            role_name: Name of the role to assign
        """
        pass

    @abstractmethod
    async def remove_role(self, user_id: str, role_name: str) -> None:
        """Remove a role from a user.

        Args:
            user_id: ID of the user
            role_name: Name of the role to remove
        """
        pass
