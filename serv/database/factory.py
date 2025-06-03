"""Factory loading system for database providers."""

import importlib
import inspect
from collections.abc import Callable
from typing import Any

from .exceptions import DatabaseFactoryError


class FactoryLoader:
    """
    Loads and invokes database factory functions with configuration.
    Supports both nested settings and flat parameter styles.
    """

    @staticmethod
    def load_factory(provider: str) -> Callable:
        """Load factory function from module path.

        Args:
            provider: Provider string in format "module.path:factory_function"

        Returns:
            The factory function

        Raises:
            DatabaseFactoryError: If provider cannot be loaded
        """
        try:
            if ":" not in provider:
                raise DatabaseFactoryError(
                    f"Invalid provider format '{provider}'. Expected 'module.path:function'."
                )

            module_path, function_name = provider.split(":", 1)
            module = importlib.import_module(module_path)
            factory_func = getattr(module, function_name)

            if not callable(factory_func):
                raise DatabaseFactoryError(f"Provider '{provider}' is not callable")

            return factory_func

        except (ImportError, AttributeError) as e:
            raise DatabaseFactoryError(
                f"Failed to load provider '{provider}': {str(e)}"
            ) from e

    @staticmethod
    def detect_config_style(config: dict[str, Any]) -> str:
        """Detect whether config uses nested settings or flat parameters.

        Args:
            config: Configuration dictionary

        Returns:
            Either "nested" or "flat"
        """
        return "nested" if "settings" in config else "flat"

    @staticmethod
    async def invoke_factory(
        factory: Callable, name: str, config: dict[str, Any]
    ) -> Any:
        """Invoke factory with appropriate parameter style.

        Args:
            factory: Factory function to invoke
            name: Database name
            config: Configuration for the database

        Returns:
            Database connection instance

        Raises:
            DatabaseFactoryError: If factory invocation fails
        """
        try:
            config_style = FactoryLoader.detect_config_style(config)

            if config_style == "nested":
                # Nested style: factory(name, settings={...})
                settings = config.get("settings", {})
                if inspect.iscoroutinefunction(factory):
                    return await factory(name, settings)
                else:
                    return factory(name, settings)
            else:
                # Flat style: factory(name, param1=value1, param2=value2, ...)
                args, kwargs = FactoryLoader.bind_flat_parameters(factory, config)
                if inspect.iscoroutinefunction(factory):
                    return await factory(name, *args, **kwargs)
                else:
                    return factory(name, *args, **kwargs)

        except Exception as e:
            raise DatabaseFactoryError(
                f"Failed to invoke factory for database '{name}': {str(e)}"
            ) from e

    @staticmethod
    def bind_flat_parameters(
        factory: Callable, config: dict[str, Any]
    ) -> tuple[tuple, dict]:
        """Bind flat config parameters to factory signature.

        Args:
            factory: Factory function
            config: Configuration dictionary

        Returns:
            Tuple of (args, kwargs) for function call
        """
        try:
            sig = inspect.signature(factory)
            bound_kwargs = {}

            # Skip first parameter (name) as it's handled separately
            params = list(sig.parameters.values())[1:]

            for param in params:
                if param.name in config:
                    bound_kwargs[param.name] = config[param.name]
                elif param.default is inspect.Parameter.empty:
                    # Required parameter missing
                    raise DatabaseFactoryError(
                        f"Required parameter '{param.name}' missing from config"
                    )

            return (), bound_kwargs

        except Exception as e:
            raise DatabaseFactoryError(
                f"Failed to bind parameters for factory: {str(e)}"
            ) from e
