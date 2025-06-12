"""Core data types for the authentication system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CredentialType(Enum):
    """Types of credentials supported by the auth system."""

    PASSWORD = "password"
    TOKEN = "token"
    API_KEY = "api_key"


class AuditEventType(Enum):
    """Types of audit events that can be logged."""

    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PERMISSION_CHECK = "permission_check"
    PERMISSION_DENIED = "permission_denied"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_DESTROYED = "session_destroyed"


class PolicyResult(Enum):
    """Result of a policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"


@dataclass
class Permission:
    """Represents a permission in the system."""

    name: str
    description: str | None = None
    resource: str | None = None
    action: str | None = None

    def __post_init__(self):
        """Validate permission after creation."""
        if not self.name or not self.name.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Permission name cannot be empty")


@dataclass
class Role:
    """Represents a role with associated permissions."""

    name: str
    description: str | None = None
    permissions: list[Permission] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate role after creation."""
        if not self.name or not self.name.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Role name cannot be empty")

    def has_permission(self, permission_name: str) -> bool:
        """Check if this role has a specific permission."""
        return any(perm.name == permission_name for perm in self.permissions)


@dataclass
class User:
    """Represents a user in the authentication system."""

    id: str
    username: str
    email: str | None = None
    is_active: bool = True
    roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    last_login: datetime | None = None

    def __post_init__(self):
        """Validate user after creation."""
        if not self.id or not self.id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("User ID cannot be empty")
        if not self.username or not self.username.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Username cannot be empty")


@dataclass
class Session:
    """Represents a user session."""

    id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    last_accessed: datetime | None = None

    def __post_init__(self):
        """Validate session after creation."""
        if not self.id or not self.id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Session ID cannot be empty")
        if not self.user_id or not self.user_id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("User ID cannot be empty")

    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the session is valid (active and not expired)."""
        return self.is_active and not self.is_expired()


@dataclass
class Credentials:
    """Represents user credentials."""

    id: str
    user_id: str
    type: CredentialType
    data: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate credentials after creation."""
        if not self.id or not self.id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Credential ID cannot be empty")
        if not self.user_id or not self.user_id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("User ID cannot be empty")
        if not self.data:
            from .exceptions import AuthValidationError

            raise AuthValidationError("Credential data cannot be empty")

    def is_expired(self) -> bool:
        """Check if the credentials have expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the credentials are valid (active and not expired)."""
        return self.is_active and not self.is_expired()


@dataclass
class AuditEvent:
    """Represents an audit event."""

    id: str
    event_type: AuditEventType
    user_id: str | None = None
    session_id: str | None = None
    resource: str | None = None
    action: str | None = None
    result: PolicyResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: str | None = None
    user_agent: str | None = None

    def __post_init__(self):
        """Validate audit event after creation."""
        if not self.id or not self.id.strip():
            from .exceptions import AuthValidationError

            raise AuthValidationError("Audit event ID cannot be empty")
