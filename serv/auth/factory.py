"""
Auth system factory for loading and configuring concrete auth implementations.

This module provides a factory system for instantiating auth components based on
configuration. It supports dynamic loading of backends specified in YAML config.
"""

import importlib
from typing import Any, TypeVar

from bevy import Container, get_registry

from .auth_provider import AuthProvider
from .credential_vault import CredentialVault
from .rate_limiter import RateLimiter
from .session_manager import SessionManager
from .token_service import TokenService

T = TypeVar("T")


class AuthConfigError(Exception):
    """Raised when auth configuration is invalid."""

    pass


class BackendLoader:
    """Loads backend classes from module paths."""

    @staticmethod
    def load_class(module_path: str) -> type:
        """
        Load a class from a module path like 'module.path:ClassName'.

        Args:
            module_path: Module path in format 'module.path:ClassName'

        Returns:
            The loaded class

        Raises:
            AuthConfigError: If the module or class cannot be loaded
        """
        try:
            if ":" not in module_path:
                raise AuthConfigError(
                    f"Invalid module path format: {module_path}. Expected 'module:class'"
                )

            module_name, class_name = module_path.rsplit(":", 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)

            return cls
        except ImportError as e:
            raise AuthConfigError(
                f"Could not import module '{module_name}': {e}"
            ) from e
        except AttributeError as e:
            raise AuthConfigError(
                f"Class '{class_name}' not found in module '{module_name}': {e}"
            ) from e


class AuthSystemFactory:
    """Factory for creating and configuring auth system components."""

    def __init__(self, container: Container | None = None):
        """
        Initialize the auth factory.

        Args:
            container: DI container for registering services. If None, uses global registry.
        """
        self.container = container or get_registry().create_container()
        self._loader = BackendLoader()

    def create_auth_provider(self, config: dict[str, Any]) -> AuthProvider:
        """
        Create an auth provider from configuration.

        Args:
            config: Provider configuration containing 'type' and 'config' keys

        Returns:
            Configured AuthProvider instance

        Raises:
            AuthConfigError: If configuration is invalid
        """
        if "type" not in config:
            raise AuthConfigError("Auth provider configuration missing 'type' field")

        provider_type = config["type"]
        provider_config = config.get("config", {})

        # Map provider types to module paths
        provider_map = {
            "jwt": "serv.bundled.auth.providers.jwt_provider:JwtAuthProvider",
            # Add more provider types as they're implemented
        }

        if provider_type not in provider_map:
            raise AuthConfigError(f"Unknown auth provider type: {provider_type}")

        provider_class = self._loader.load_class(provider_map[provider_type])

        # Validate that the class is actually an AuthProvider
        if not issubclass(provider_class, AuthProvider):
            raise AuthConfigError(f"Class {provider_class} is not an AuthProvider")

        return provider_class(provider_config)

    def create_session_storage(self, config: dict[str, Any]) -> SessionManager:
        """
        Create a session storage from configuration.

        Args:
            config: Storage configuration containing 'backend' and other config

        Returns:
            Configured SessionManager instance

        Raises:
            AuthConfigError: If configuration is invalid
        """
        if "backend" not in config:
            raise AuthConfigError(
                "Session storage configuration missing 'backend' field"
            )

        backend_path = config["backend"]
        storage_class = self._loader.load_class(backend_path)

        # Validate that the class is actually a SessionManager
        if not issubclass(storage_class, SessionManager):
            raise AuthConfigError(f"Class {storage_class} is not a SessionManager")

        # Extract config excluding the backend field
        storage_config = {k: v for k, v in config.items() if k != "backend"}

        return storage_class(storage_config)

    def create_credential_vault(self, config: dict[str, Any]) -> CredentialVault:
        """
        Create a credential vault from configuration.

        Args:
            config: Vault configuration containing 'backend' and other config

        Returns:
            Configured CredentialVault instance

        Raises:
            AuthConfigError: If configuration is invalid
        """
        if "backend" not in config:
            raise AuthConfigError(
                "Credential vault configuration missing 'backend' field"
            )

        backend_path = config["backend"]
        vault_class = self._loader.load_class(backend_path)

        # Validate that the class is actually a CredentialVault
        if not issubclass(vault_class, CredentialVault):
            raise AuthConfigError(f"Class {vault_class} is not a CredentialVault")

        # Extract config excluding the backend field
        vault_config = {k: v for k, v in config.items() if k != "backend"}

        return vault_class(vault_config)

    def create_rate_limiter(self, config: dict[str, Any]) -> RateLimiter:
        """
        Create a rate limiter from configuration.

        Args:
            config: Rate limiter configuration containing 'backend' and other config

        Returns:
            Configured RateLimiter instance

        Raises:
            AuthConfigError: If configuration is invalid
        """
        if "backend" not in config:
            raise AuthConfigError("Rate limiter configuration missing 'backend' field")

        backend_path = config["backend"]
        limiter_class = self._loader.load_class(backend_path)

        # Validate that the class is actually a RateLimiter
        if not issubclass(limiter_class, RateLimiter):
            raise AuthConfigError(f"Class {limiter_class} is not a RateLimiter")

        # Extract config excluding the backend field
        limiter_config = {k: v for k, v in config.items() if k != "backend"}

        return limiter_class(limiter_config)

    def create_token_service(self, config: dict[str, Any]) -> TokenService:
        """
        Create a token service from configuration.

        Args:
            config: Token service configuration containing 'backend' and other config

        Returns:
            Configured TokenService instance

        Raises:
            AuthConfigError: If configuration is invalid
        """
        if "backend" not in config:
            raise AuthConfigError("Token service configuration missing 'backend' field")

        backend_path = config["backend"]
        service_class = self._loader.load_class(backend_path)

        # Validate that the class is actually a TokenService
        if not issubclass(service_class, TokenService):
            raise AuthConfigError(f"Class {service_class} is not a TokenService")

        # Extract config excluding the backend field
        service_config = {k: v for k, v in config.items() if k != "backend"}

        return service_class(service_config)

    def configure_auth_system(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        """
        Configure the complete auth system from configuration.

        This method creates all auth components and registers them in the DI container
        using their abstract base classes as keys, enabling loose coupling through DI.

        Args:
            auth_config: Complete auth configuration dictionary

        Returns:
            Dictionary mapping component names to their instances

        Raises:
            AuthConfigError: If configuration is invalid
        """
        components = {}

        # Create auth providers
        if "providers" in auth_config:
            providers = []
            for provider_config in auth_config["providers"]:
                provider = self.create_auth_provider(provider_config)
                providers.append(provider)
                # Register in DI container using the abstract base class as key
                self.container.add(AuthProvider, provider)
            components["providers"] = providers

        # Create session storage
        if "storage" in auth_config:
            storage = self.create_session_storage(auth_config["storage"])
            components["storage"] = storage
            # Register in DI container using the abstract base class as key
            self.container.add(SessionManager, storage)

        # Create credential vault
        if "credential_vault" in auth_config:
            vault = self.create_credential_vault(auth_config["credential_vault"])
            components["credential_vault"] = vault
            # Register in DI container using the abstract base class as key
            self.container.add(CredentialVault, vault)

        # Create rate limiter
        if "rate_limiting" in auth_config:
            limiter = self.create_rate_limiter(auth_config["rate_limiting"])
            components["rate_limiter"] = limiter
            # Register in DI container using the abstract base class as key
            self.container.add(RateLimiter, limiter)

        # Create token service (if configured separately)
        if "token_service" in auth_config:
            token_service = self.create_token_service(auth_config["token_service"])
            components["token_service"] = token_service
            # Register in DI container using the abstract base class as key
            self.container.add(TokenService, token_service)

        return components

    def get_configured_container(self) -> Container:
        """
        Get the container with all auth services registered.

        Returns:
            Container instance with auth services
        """
        return self.container


def create_auth_system(
    auth_config: dict[str, Any], container: Container | None = None
) -> dict[str, Any]:
    """
    Convenience function to create and configure an auth system.

    Args:
        auth_config: Auth configuration dictionary
        container: Optional DI container. If None, creates a new one.

    Returns:
        Dictionary mapping component names to their instances

    Raises:
        AuthConfigError: If configuration is invalid
    """
    factory = AuthSystemFactory(container)
    return factory.configure_auth_system(auth_config)
