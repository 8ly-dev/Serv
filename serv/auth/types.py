"""
Shared data types and enums for the Serv authentication framework.

This module defines all the core data structures used throughout the auth system,
including status codes, result objects, and security-related data classes.

Security considerations:
- All sensitive data should be marked appropriately
- Credentials should never be logged or exposed in string representations
- Timing-sensitive operations should use consistent data structures
"""

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AuthStatus(Enum):
    """Standardized authentication status codes."""

    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_DISABLED = "account_disabled"
    SESSION_EXPIRED = "session_expired"
    INVALID_TOKEN = "invalid_token"
    RATE_LIMITED = "rate_limited"
    PERMISSION_DENIED = "permission_denied"
    INTERNAL_ERROR = "internal_error"
    VALIDATION_ERROR = "validation_error"
    MFA_REQUIRED = "mfa_required"


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    status: AuthStatus
    user_id: str | None = None
    user_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def __post_init__(self):
        """Security: Ensure sensitive data isn't accidentally exposed."""
        if self.status == AuthStatus.SUCCESS and not self.user_id:
            raise ValueError("Successful authentication must include user_id")


@dataclass
class ValidationResult:
    """Result of credential validation."""

    is_valid: bool
    user_id: str | None = None
    user_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class RefreshResult:
    """Result of session/token refresh operation."""

    success: bool
    new_token: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class Session:
    """User session with security metadata."""

    session_id: str
    user_id: str
    user_context: dict[str, Any]
    device_fingerprint: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_id: str,
        user_context: dict[str, Any],
        device_fingerprint: str,
        timeout_seconds: int = 3600,
    ) -> "Session":
        """Create a new session with secure defaults."""
        now = datetime.now(UTC)
        session_id = secrets.token_urlsafe(32)  # Cryptographically secure

        return cls(
            session_id=session_id,
            user_id=user_id,
            user_context=user_context.copy(),  # Defensive copy
            device_fingerprint=device_fingerprint,
            created_at=now,
            expires_at=datetime.fromtimestamp(now.timestamp() + timeout_seconds, UTC),
            last_activity=now,
        )

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(UTC) >= self.expires_at

    def refresh_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(UTC)


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    allowed: bool
    reason: str
    policy_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    required_permissions: set[str] = field(default_factory=set)


@dataclass
class Token:
    """Security token with metadata."""

    token_id: str
    token_value: str
    token_type: str  # "access", "refresh", "api_key", etc.
    user_id: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        token_value: str,
        token_type: str,
        user_id: str,
        payload: dict[str, Any],
        expires_in: int | None = None,
    ) -> "Token":
        """Create a new token with secure defaults."""
        now = datetime.now(UTC)
        token_id = secrets.token_urlsafe(16)

        expires_at = None
        if expires_in is not None:
            expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, UTC)

        return cls(
            token_id=token_id,
            token_value=token_value,
            token_type=token_type,
            user_id=user_id,
            payload=payload.copy(),  # Defensive copy
            created_at=now,
            expires_at=expires_at,
        )

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    def __repr__(self) -> str:
        """Security: Never expose token value in string representation."""
        return (
            f"Token(token_id='{self.token_id}', "
            f"token_type='{self.token_type}', "
            f"user_id='{self.user_id}', "
            f"expires_at={self.expires_at})"
        )


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: int | None = None  # Seconds until next attempt allowed
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """Immutable audit log event."""

    audit_id: str
    timestamp: datetime
    event_type: str
    actor_info: dict[str, Any]
    resource_info: dict[str, Any]
    outcome: str  # "success", "failure", "error"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        event_type: str,
        actor_info: dict[str, Any],
        resource_info: dict[str, Any],
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> "AuditEvent":
        """Create a new audit event with secure defaults."""
        audit_id = secrets.token_urlsafe(16)
        timestamp = datetime.now(UTC)

        return cls(
            audit_id=audit_id,
            timestamp=timestamp,
            event_type=event_type,
            actor_info=actor_info.copy(),  # Defensive copy
            resource_info=resource_info.copy(),  # Defensive copy
            outcome=outcome,
            metadata=metadata.copy() if metadata else {},
        )

    def __post_init__(self):
        """Validate audit event data."""
        if self.outcome not in ("success", "failure", "error"):
            raise ValueError(f"Invalid outcome: {self.outcome}")

        # Security: Ensure no sensitive data in actor_info
        sensitive_keys = {"password", "token", "secret", "key"}
        for key in self.actor_info:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Sensitive data not allowed in actor_info: {key}")


@dataclass
class Role:
    """User role with permissions."""

    name: str
    permissions: set[str]
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if role has specific permission."""
        return permission in self.permissions

    def add_permission(self, permission: str) -> None:
        """Add permission to role."""
        self.permissions.add(permission)

    def remove_permission(self, permission: str) -> None:
        """Remove permission from role."""
        self.permissions.discard(permission)


@dataclass
class Permission:
    """Individual permission definition."""

    name: str
    description: str | None = None
    resource_type: str | None = None
    action: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Credential:
    """Stored credential with security metadata."""

    credential_id: str
    user_id: str
    credential_type: str  # "password", "api_key", "certificate", etc.
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls, user_id: str, credential_type: str, expires_in: int | None = None
    ) -> "Credential":
        """Create new credential record with secure defaults."""
        now = datetime.now(UTC)
        credential_id = secrets.token_urlsafe(16)

        expires_at = None
        if expires_in is not None:
            expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, UTC)

        return cls(
            credential_id=credential_id,
            user_id=user_id,
            credential_type=credential_type,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

    def is_expired(self) -> bool:
        """Check if credential is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    def __repr__(self) -> str:
        """Security: Never expose credential data in string representation."""
        return (
            f"Credential(credential_id='{self.credential_id}', "
            f"user_id='{self.user_id}', "
            f"credential_type='{self.credential_type}', "
            f"is_active={self.is_active})"
        )
