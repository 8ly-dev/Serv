"""Auth system bootstrap for setting up providers from configuration."""

from typing import Dict, Type

from bevy import Container

from ..config.schema import AuthConfig
from ..exceptions import ConfigurationError, ProviderInitializationError
from ..providers.audit import AuditProvider
from ..providers.auth import AuthProvider
from ..providers.base import BaseProvider
from ..providers.credential import CredentialProvider
from ..providers.session import SessionProvider
from ..providers.user import UserProvider
from .factories import (
    AuditProviderFactory,
    CredentialProviderFactory,
    PolicyProviderFactory,
    SessionProviderFactory,
    UserProviderFactory,
)


class AuthSystemBootstrap:
    """Bootstraps the authentication system from configuration."""

    def __init__(self, config: AuthConfig):
        """Initialize the bootstrap with configuration.

        Args:
            config: Authentication configuration
        """
        self.config = config
        self.factories = {
            "credential": CredentialProviderFactory(),
            "session": SessionProviderFactory(),
            "user": UserProviderFactory(),
            "audit": AuditProviderFactory(),
            "policy": PolicyProviderFactory(),
        }

    async def setup_providers(self, container: Container) -> None:
        """Set up all auth providers in the container.

        Args:
            container: Dependency injection container

        Raises:
            ConfigurationError: If configuration is invalid
            ProviderInitializationError: If provider setup fails
        """
        if not self.config.enabled:
            # Auth system is disabled, don't set up providers
            return

        try:
            # Create providers in dependency order
            # Audit provider first (no dependencies)
            audit_provider = await self._create_audit_provider(container)

            # Credential provider (may depend on audit)
            credential_provider = await self._create_credential_provider(container)

            # Session provider (may depend on audit)
            session_provider = await self._create_session_provider(container)

            # User provider (may depend on audit)
            user_provider = await self._create_user_provider(container)

            # Policy provider (may depend on user and audit)
            policy_provider = await self._create_policy_provider(container)

            # Create main auth provider (depends on all others)
            auth_provider = await self._create_main_auth_provider(
                credential_provider, session_provider, user_provider, audit_provider
            )

            # Register all providers in container
            container.add(AuditProvider, audit_provider)
            container.add(CredentialProvider, credential_provider)
            container.add(SessionProvider, session_provider)
            container.add(UserProvider, user_provider)
            container.add(AuthProvider, auth_provider)

            # Register policy provider (when we have the interface)
            if policy_provider:
                container.add(BaseProvider, policy_provider, qualifier="policy")

            # Set up any additional infrastructure
            await self._setup_additional_infrastructure(container)

        except (ConfigurationError, ProviderInitializationError):
            raise
        except Exception as e:
            raise ProviderInitializationError(
                "Failed to setup auth system"
            ) from e

    async def _create_credential_provider(
        self, container: Container
    ) -> CredentialProvider:
        """Create credential provider from configuration."""
        config = self.config.providers.credential.model_dump()
        factory = self.factories["credential"]

        if not factory.validate_config(config):
            raise ConfigurationError("Invalid credential provider configuration")

        return factory.create(config, container)

    async def _create_session_provider(self, container: Container) -> SessionProvider:
        """Create session provider from configuration."""
        config = self.config.providers.session.model_dump()
        factory = self.factories["session"]

        if not factory.validate_config(config):
            raise ConfigurationError("Invalid session provider configuration")

        return factory.create(config, container)

    async def _create_user_provider(self, container: Container) -> UserProvider:
        """Create user provider from configuration."""
        config = self.config.providers.user.model_dump()
        factory = self.factories["user"]

        if not factory.validate_config(config):
            raise ConfigurationError("Invalid user provider configuration")

        return factory.create(config, container)

    async def _create_audit_provider(self, container: Container) -> AuditProvider:
        """Create audit provider from configuration."""
        config = self.config.providers.audit.model_dump()
        factory = self.factories["audit"]

        if not factory.validate_config(config):
            raise ConfigurationError("Invalid audit provider configuration")

        return factory.create(config, container)

    async def _create_policy_provider(
        self, container: Container
    ) -> BaseProvider | None:
        """Create policy provider from configuration."""
        config = self.config.providers.policy.model_dump()
        factory = self.factories["policy"]

        if not factory.validate_config(config):
            raise ConfigurationError("Invalid policy provider configuration")

        return factory.create(config, container)

    async def _create_main_auth_provider(
        self,
        credential_provider: CredentialProvider,
        session_provider: SessionProvider,
        user_provider: UserProvider,
        audit_provider: AuditProvider,
    ) -> AuthProvider:
        """Create the main auth provider that orchestrates all others.

        Creates a StandardAuthProvider that coordinates between all the
        individual providers. The StandardAuthProvider is a scaffold
        implementation that will be fully implemented in Phase 3.
        """
        from serv.bundled.auth.auth import StandardAuthProvider

        return StandardAuthProvider(
            credential_provider=credential_provider,
            session_provider=session_provider,
            user_provider=user_provider,
            audit_provider=audit_provider,
        )

    async def _setup_additional_infrastructure(self, container: Container) -> None:
        """Set up additional infrastructure like database models.

        Args:
            container: Dependency injection container
        """
        # Check if any providers are using database
        database_qualifiers = set()

        for provider_config in [
            self.config.providers.credential,
            self.config.providers.session,
            self.config.providers.user,
            self.config.providers.audit,
        ]:
            if provider_config.provider == "database":
                qualifier = provider_config.config.get("database_qualifier")
                if qualifier:
                    database_qualifiers.add(qualifier)

        # Set up models for each database
        for qualifier in database_qualifiers:
            await self._setup_database_models(container, qualifier)

    async def _setup_database_models(
        self, container: Container, qualifier: str
    ) -> None:
        """Set up database models for auth providers that need them.

        Args:
            container: Dependency injection container
            qualifier: Database qualifier name
        """
        try:
            # This will be implemented when we create the database providers
            # For now, this is a placeholder
            pass

        except Exception as e:
            raise ConfigurationError(
                f"Failed to setup auth models for database '{qualifier}'"
            ) from e

    def validate_configuration(self) -> None:
        """Validate the complete auth configuration.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not self.config.enabled:
            return

        # Validate each provider configuration
        for provider_name, factory in self.factories.items():
            provider_config = getattr(self.config.providers, provider_name)
            config_dict = provider_config.model_dump()

            if not factory.validate_config(config_dict):
                raise ConfigurationError(
                    f"Invalid {provider_name} provider configuration"
                )

    def get_provider_info(self) -> Dict[str, Dict[str, str]]:
        """Get information about configured providers.

        Returns:
            Dictionary mapping provider types to their configurations
        """
        if not self.config.enabled:
            return {}

        info = {}
        for provider_name in self.factories.keys():
            provider_config = getattr(self.config.providers, provider_name)
            info[provider_name] = {
                "provider": provider_config.provider,
                "type": "bundled"
                if ":" not in provider_config.provider
                else "external",
            }

        return info
