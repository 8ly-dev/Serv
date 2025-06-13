"""Authentication and authorization system for Serv framework."""

from .config import (
    AuthConfig,
    ExtensionAuthConfig,
    ProvidersConfig,
    ProviderConfig,
    parse_auth_config,
    parse_extension_auth_config,
)
from .exceptions import (
    ConfigurationError,
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
    "ExtensionAuthConfig",
    "ProvidersConfig", 
    "ProviderConfig",
    "parse_auth_config",
    "parse_extension_auth_config",
    "ConfigurationError",
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
