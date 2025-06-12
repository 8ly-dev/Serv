"""Provider factory system for authentication."""

from .base import (
    ProviderFactory,
)

from .registry import (
    ProviderRegistry,
)

from .factories import (
    CredentialProviderFactory,
    SessionProviderFactory,
    UserProviderFactory,
    AuditProviderFactory,
    PolicyProviderFactory,
)

from .bootstrap import (
    AuthSystemBootstrap,
)

__all__ = [
    # Base factory
    "ProviderFactory",
    # Registry
    "ProviderRegistry",
    # Specific factories
    "CredentialProviderFactory",
    "SessionProviderFactory",
    "UserProviderFactory",
    "AuditProviderFactory",
    "PolicyProviderFactory",
    # Bootstrap
    "AuthSystemBootstrap",
]
