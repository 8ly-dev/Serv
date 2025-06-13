"""Specific provider factories for each provider type."""

from typing import Any, Dict, Type

from bevy import Container

from ..exceptions import ConfigurationError
from ..providers.audit import AuditProvider
from ..providers.auth import AuthProvider
from ..providers.base import BaseProvider
from ..providers.credential import CredentialProvider
from ..providers.session import SessionProvider
from ..providers.user import UserProvider
from .base import ProviderFactory
from .registry import provider_registry


class CredentialProviderFactory(ProviderFactory):
    """Factory for credential providers."""

    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the credential provider base type."""
        return CredentialProvider

    def create(
        self, config: Dict[str, Any], container: Container
    ) -> CredentialProvider:
        """Create credential provider from configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            raise ConfigurationError("Credential provider specification is required")

        # Resolve provider import string
        import_string = provider_registry.resolve_provider_import(
            "credential", provider_spec
        )
        if not import_string:
            available = provider_registry.list_available_providers("credential")
            raise ConfigurationError(
                f"Unknown credential provider: {provider_spec}. "
                f"Available providers: {', '.join(available.keys())}"
            )

        return self.create_from_import_string(import_string, config, container)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate credential provider configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            return False

        # If it's an import string, validate it
        if ":" in provider_spec:
            return self.validate_import_string(provider_spec, CredentialProvider)

        # Check if it's a known provider type
        import_string = provider_registry.resolve_provider_import(
            "credential", provider_spec
        )
        return import_string is not None


class SessionProviderFactory(ProviderFactory):
    """Factory for session providers."""

    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the session provider base type."""
        return SessionProvider

    def create(self, config: Dict[str, Any], container: Container) -> SessionProvider:
        """Create session provider from configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            raise ConfigurationError("Session provider specification is required")

        # Resolve provider import string
        import_string = provider_registry.resolve_provider_import(
            "session", provider_spec
        )
        if not import_string:
            available = provider_registry.list_available_providers("session")
            raise ConfigurationError(
                f"Unknown session provider: {provider_spec}. "
                f"Available providers: {', '.join(available.keys())}"
            )

        return self.create_from_import_string(import_string, config, container)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate session provider configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            return False

        # If it's an import string, validate it
        if ":" in provider_spec:
            return self.validate_import_string(provider_spec, SessionProvider)

        # Check if it's a known provider type
        import_string = provider_registry.resolve_provider_import(
            "session", provider_spec
        )
        return import_string is not None


class UserProviderFactory(ProviderFactory):
    """Factory for user providers."""

    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the user provider base type."""
        return UserProvider

    def create(self, config: Dict[str, Any], container: Container) -> UserProvider:
        """Create user provider from configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            raise ConfigurationError("User provider specification is required")

        # Resolve provider import string
        import_string = provider_registry.resolve_provider_import("user", provider_spec)
        if not import_string:
            available = provider_registry.list_available_providers("user")
            raise ConfigurationError(
                f"Unknown user provider: {provider_spec}. "
                f"Available providers: {', '.join(available.keys())}"
            )

        return self.create_from_import_string(import_string, config, container)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate user provider configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            return False

        # If it's an import string, validate it
        if ":" in provider_spec:
            return self.validate_import_string(provider_spec, UserProvider)

        # Check if it's a known provider type
        import_string = provider_registry.resolve_provider_import("user", provider_spec)
        return import_string is not None


class AuditProviderFactory(ProviderFactory):
    """Factory for audit providers."""

    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the audit provider base type."""
        return AuditProvider

    def create(self, config: Dict[str, Any], container: Container) -> AuditProvider:
        """Create audit provider from configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            raise ConfigurationError("Audit provider specification is required")

        # Resolve provider import string
        import_string = provider_registry.resolve_provider_import(
            "audit", provider_spec
        )
        if not import_string:
            available = provider_registry.list_available_providers("audit")
            raise ConfigurationError(
                f"Unknown audit provider: {provider_spec}. "
                f"Available providers: {', '.join(available.keys())}"
            )

        return self.create_from_import_string(import_string, config, container)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate audit provider configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            return False

        # If it's an import string, validate it
        if ":" in provider_spec:
            return self.validate_import_string(provider_spec, AuditProvider)

        # Check if it's a known provider type
        import_string = provider_registry.resolve_provider_import(
            "audit", provider_spec
        )
        return import_string is not None


class PolicyProviderFactory(ProviderFactory):
    """Factory for policy providers."""

    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the policy provider base type."""
        # For now, return BaseProvider since we don't have a PolicyProvider base class yet
        # This will be updated when we implement the policy system
        return BaseProvider

    def create(self, config: Dict[str, Any], container: Container) -> BaseProvider:
        """Create policy provider from configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            raise ConfigurationError("Policy provider specification is required")

        # Resolve provider import string
        import_string = provider_registry.resolve_provider_import(
            "policy", provider_spec
        )
        if not import_string:
            available = provider_registry.list_available_providers("policy")
            raise ConfigurationError(
                f"Unknown policy provider: {provider_spec}. "
                f"Available providers: {', '.join(available.keys())}"
            )

        return self.create_from_import_string(import_string, config, container)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate policy provider configuration."""
        provider_spec = config.get("provider")
        if not provider_spec:
            return False

        # If it's an import string, validate it
        if ":" in provider_spec:
            return self.validate_import_string(provider_spec, BaseProvider)

        # Check if it's a known provider type
        import_string = provider_registry.resolve_provider_import(
            "policy", provider_spec
        )
        return import_string is not None
