"""Authentication and authorization system for Serv framework."""

from .exceptions import (
    AuditError,
    AuthenticationError,
    AuthError,
    AuthorizationError,
    AuthValidationError,
    InvalidCredentialsError,
    PermissionDeniedError,
    SessionExpiredError,
)
from .types import (
    AuditEventType,
    Credentials,
    CredentialType,
    Permission,
    PolicyResult,
    Role,
    Session,
    User,
)

__all__ = [
    # Types
    "User",
    "Session",
    "Credentials",
    "Permission",
    "Role",
    "CredentialType",
    "AuditEventType",
    "PolicyResult",
    # Exceptions
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "AuthValidationError",
    "SessionExpiredError",
    "InvalidCredentialsError",
    "PermissionDeniedError",
    "AuditError",
]
