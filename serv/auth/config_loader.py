"""
Auth configuration loader for Serv applications.

This module provides integration between the Serv configuration system and
the auth factory, automatically loading and registering auth services based
on configuration.
"""

import logging
from typing import Any

from bevy import Container

from .factory import AuthConfigError, AuthSystemFactory

logger = logging.getLogger(__name__)


class AuthConfigLoader:
    """Loads and configures auth system from Serv app configuration."""

    def __init__(self, container: Container):
        """
        Initialize the auth config loader.

        Args:
            container: DI container for registering auth services
        """
        self.container = container
        self.factory = AuthSystemFactory(container)
        self._configured = False

    def load_auth_config(self, app_config: dict[str, Any]) -> None:
        """
        Load auth configuration from app config and register services.

        Args:
            app_config: Full app configuration dictionary

        Raises:
            AuthConfigError: If auth configuration is invalid
        """
        if self._configured:
            logger.warning("Auth system already configured, skipping")
            return

        auth_config = app_config.get("auth")
        if not auth_config:
            logger.info("No auth configuration found, skipping auth system setup")
            return

        try:
            logger.info("Configuring auth system from configuration")
            components = self.factory.configure_auth_system(auth_config)

            # Log what was configured
            for component_type, component in components.items():
                if isinstance(component, list):
                    logger.info(f"Configured {len(component)} {component_type}")
                    for i, item in enumerate(component):
                        logger.info(f"  {i + 1}. {type(item).__name__}")
                else:
                    logger.info(
                        f"Configured {component_type}: {type(component).__name__}"
                    )

            self._configured = True
            logger.info("Auth system configuration completed successfully")

        except AuthConfigError as e:
            logger.error(f"Auth configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during auth configuration: {e}")
            raise AuthConfigError(f"Failed to configure auth system: {e}") from e

    def is_configured(self) -> bool:
        """
        Check if auth system has been configured.

        Returns:
            True if auth system is configured
        """
        return self._configured

    def get_container(self) -> Container:
        """
        Get the container with auth services registered.

        Returns:
            Container instance with auth services
        """
        return self.container


def configure_auth_from_app_config(
    app_config: dict[str, Any], container: Container
) -> AuthConfigLoader:
    """
    Convenience function to configure auth system from app config.

    Args:
        app_config: Full app configuration dictionary
        container: DI container for registering auth services

    Returns:
        Configured AuthConfigLoader instance

    Raises:
        AuthConfigError: If auth configuration is invalid
    """
    loader = AuthConfigLoader(container)
    loader.load_auth_config(app_config)
    return loader
