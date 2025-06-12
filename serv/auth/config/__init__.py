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
    parse_auth_config,
    parse_extension_auth_config,
    merge_extension_configs,
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
    # Loading functions
    "parse_auth_config", 
    "parse_extension_auth_config",
    "merge_extension_configs",
    # Validation
    "AuthConfigValidator",
]
