"""Provider registry for managing bundled and external providers."""

from typing import Dict, Type

from ..providers.base import BaseProvider


class ProviderRegistry:
    """Registry for managing provider implementations."""

    def __init__(self):
        """Initialize the provider registry."""
        self._bundled_implementations: Dict[str, Dict[str, str]] = {}
        self._external_implementations: Dict[str, Dict[str, str]] = {}
        self._initialize_bundled_providers()

    def _initialize_bundled_providers(self) -> None:
        """Initialize the registry with bundled provider implementations."""

        # Credential providers
        self._bundled_implementations["credential"] = {
            "memory": "serv.bundled.auth.memory.credential:MemoryCredentialProvider",
            "database": "serv.bundled.auth.database.credential:DatabaseCredentialProvider",
        }

        # Session providers
        self._bundled_implementations["session"] = {
            "memory": "serv.bundled.auth.memory.session:MemorySessionProvider",
            "database": "serv.bundled.auth.database.session:DatabaseSessionProvider",
        }

        # User providers
        self._bundled_implementations["user"] = {
            "memory": "serv.bundled.auth.memory.user:MemoryUserProvider",
            "database": "serv.bundled.auth.database.user:DatabaseUserProvider",
        }

        # Audit providers
        self._bundled_implementations["audit"] = {
            "memory": "serv.bundled.auth.memory.audit:MemoryAuditProvider",
            "database": "serv.bundled.auth.database.audit:DatabaseAuditProvider",
            "file": "serv.bundled.auth.file.audit:FileAuditProvider",
        }

        # Policy providers
        self._bundled_implementations["policy"] = {
            "rbac": "serv.bundled.auth.policy.rbac:RBACPolicyProvider",
            "abac": "serv.bundled.auth.policy.abac:ABACPolicyProvider",
        }

    def get_bundled_implementations(self, provider_type: str) -> Dict[str, str]:
        """Get bundled implementations for a provider type.

        Args:
            provider_type: Type of provider (credential, session, user, audit, policy)

        Returns:
            Dictionary mapping provider names to import strings
        """
        return self._bundled_implementations.get(provider_type, {}).copy()

    def get_external_implementations(self, provider_type: str) -> Dict[str, str]:
        """Get external implementations for a provider type.

        Args:
            provider_type: Type of provider (credential, session, user, audit, policy)

        Returns:
            Dictionary mapping provider names to import strings
        """
        return self._external_implementations.get(provider_type, {}).copy()

    def register_external_provider(
        self, provider_type: str, provider_name: str, import_string: str
    ) -> None:
        """Register an external provider implementation.

        Args:
            provider_type: Type of provider (credential, session, user, audit, policy)
            provider_name: Name for the provider implementation
            import_string: Import path in format 'module.path:Class'
        """
        if provider_type not in self._external_implementations:
            self._external_implementations[provider_type] = {}

        self._external_implementations[provider_type][provider_name] = import_string

    def unregister_external_provider(
        self, provider_type: str, provider_name: str
    ) -> bool:
        """Unregister an external provider implementation.

        Args:
            provider_type: Type of provider
            provider_name: Name of the provider implementation

        Returns:
            True if provider was found and removed, False otherwise
        """
        if provider_type in self._external_implementations:
            return (
                self._external_implementations[provider_type].pop(provider_name, None)
                is not None
            )
        return False

    def resolve_provider_import(
        self, provider_type: str, provider_spec: str
    ) -> str | None:
        """Resolve a provider specification to an import string.

        Args:
            provider_type: Type of provider
            provider_spec: Provider specification (name or import string)

        Returns:
            Import string if found, None otherwise
        """
        # If it's already an import string (contains ':'), return as-is
        if ":" in provider_spec:
            return provider_spec

        # Check bundled implementations first
        bundled = self._bundled_implementations.get(provider_type, {})
        if provider_spec in bundled:
            return bundled[provider_spec]

        # Check external implementations
        external = self._external_implementations.get(provider_type, {})
        if provider_spec in external:
            return external[provider_spec]

        # Not found
        return None

    def is_bundled_provider(self, provider_type: str, provider_name: str) -> bool:
        """Check if a provider is a bundled implementation.

        Args:
            provider_type: Type of provider
            provider_name: Name of the provider

        Returns:
            True if it's a bundled provider, False otherwise
        """
        bundled = self._bundled_implementations.get(provider_type, {})
        return provider_name in bundled

    def list_available_providers(self, provider_type: str) -> Dict[str, str]:
        """List all available providers for a type.

        Args:
            provider_type: Type of provider

        Returns:
            Dictionary mapping provider names to their types (bundled/external)
        """
        result = {}

        # Add bundled providers
        bundled = self._bundled_implementations.get(provider_type, {})
        for name in bundled:
            result[name] = "bundled"

        # Add external providers
        external = self._external_implementations.get(provider_type, {})
        for name in external:
            result[name] = "external"

        return result

    def get_supported_provider_types(self) -> list[str]:
        """Get list of supported provider types.

        Returns:
            List of provider type names
        """
        return list(self._bundled_implementations.keys())


# Global provider registry instance
provider_registry = ProviderRegistry()
