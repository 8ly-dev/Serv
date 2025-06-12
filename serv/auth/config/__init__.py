"""Configuration system for authentication."""

from .schema import (
    AuthConfig,
    ProvidersConfig,
    ProviderConfig,
    SecurityConfig,
    DevelopmentConfig,
    ExtensionAuthConfig,
    PoliciesConfig,
    RouterConfig,
    RouteConfig,
    PolicyConfig,
    PolicyType,
    PermissionDef,
    RoleDef,
    AuditConfig,
)

from .loader import (
    AuthConfigLoader,
    ConfigurationError,
)

from .validation import (
    AuthConfigValidator,
)

__all__ = [
    # Schema models
    "AuthConfig",
    "ProvidersConfig",
    "ProviderConfig",
    "SecurityConfig",
    "DevelopmentConfig",
    "ExtensionAuthConfig",
    "PoliciesConfig",
    "RouterConfig",
    "RouteConfig",
    "PolicyConfig",
    "PolicyType",
    "PermissionDef",
    "RoleDef",
    "AuditConfig",
    # Loading and validation
    "AuthConfigLoader",
    "ConfigurationError",
    "AuthConfigValidator",
]
