"""Authentication and authorization system for Serv framework."""

from .config import (
    AuthConfig,
    AuthConfigLoader,
    ConfigurationError,
    ExtensionAuthConfig,
    ProvidersConfig,
    ProviderConfig,
)
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
    # Configuration
    "AuthConfig",
    "AuthConfigLoader",
    "ConfigurationError",
    "ExtensionAuthConfig",
    "ProvidersConfig",
    "ProviderConfig",
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
