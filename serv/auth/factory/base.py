"""Base factory class for provider creation."""

import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

from bevy import Container

from ..exceptions import ConfigurationError, ProviderInitializationError
from ..providers.base import BaseProvider


class ProviderFactory(ABC):
    """Base factory for creating provider instances."""

    @abstractmethod
    def create(self, config: Dict[str, Any], container: Container) -> BaseProvider:
        """Create provider instance from configuration.

        Args:
            config: Provider configuration dictionary
            container: Dependency injection container

        Returns:
            Configured provider instance

        Raises:
            ConfigurationError: If configuration is invalid
            ProviderInitializationError: If provider creation fails
        """
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate provider configuration.

        Args:
            config: Provider configuration dictionary

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> Type[BaseProvider]:
        """Get the base provider type this factory creates.

        Returns:
            Provider base class type
        """
        pass

    def create_from_import_string(
        self, import_string: str, config: Dict[str, Any], container: Container
    ) -> BaseProvider:
        """Create provider from import string in format 'module.path:Class'.

        Args:
            import_string: Import path in format 'module.path:Class'
            config: Provider configuration
            container: Dependency injection container

        Returns:
            Provider instance

        Raises:
            ConfigurationError: If import string is invalid or class can't be imported
            ProviderInitializationError: If provider creation fails
        """
        try:
            module_path, class_name = import_string.split(":", 1)
        except ValueError as e:
            raise ConfigurationError(f"Invalid import string format: {import_string}") from e

        try:
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
        except ImportError as e:
            raise ConfigurationError(f"Cannot import module '{module_path}'") from e
        except AttributeError as e:
            raise ConfigurationError(
                f"Class '{class_name}' not found in module '{module_path}'"
            ) from e

        # Validate that it's the correct provider type
        expected_type = self.get_provider_type()
        if not issubclass(provider_class, expected_type):
            raise ConfigurationError(
                f"Class '{class_name}' is not a valid {expected_type.__name__} "
                f"(must inherit from {expected_type.__name__})"
            )

        # Create provider instance
        try:
            provider_config = config.get("config", {})
            return provider_class(provider_config, container)
        except Exception as e:
            raise ProviderInitializationError(
                f"Failed to initialize {class_name}: {e}"
            ) from e

    def validate_import_string(
        self, import_string: str, expected_base_class: Type
    ) -> bool:
        """Validate that an import string points to a valid provider class.

        Args:
            import_string: Import path in format 'module.path:Class'
            expected_base_class: Expected base class for validation

        Returns:
            True if import string is valid, False otherwise
        """
        try:
            module_path, class_name = import_string.split(":", 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)

            # Check if it's a subclass of the expected base class
            return issubclass(provider_class, expected_base_class)

        except (ValueError, ImportError, AttributeError, TypeError):
            return False
