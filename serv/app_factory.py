"""
Application factory for creating configured Serv apps.

This module provides a reusable factory for creating App instances with CLI-style
configuration, making it easy to create apps both in the CLI and for testing.
"""

import logging
from inspect import isclass
from pathlib import Path
from typing import Any

from serv.app import App
from serv.config import import_from_string

logger = logging.getLogger(__name__)


def create_app(
    *,
    app_module_str: str | None = None,
    config: str | None = None,
    extension_dirs: str | None = None,
    dev: bool = False,
) -> App:
    """Create a configured App instance.

    This function mirrors the CLI's app creation logic, allowing for the same
    configuration options to be used both in the CLI and programmatically.

    Args:
        app_module_str: Custom application class in the format "module.path:ClassName".
            If not provided, Serv's default App is used.
        config: Path to config file. If not provided, App uses its default.
        extension_dirs: Directory to search for extensions. If not provided, App uses its default.
        dev: Enable development mode with enhanced features.

    Returns:
        A configured App instance.

    Raises:
        ValueError: If app_module_str is not a valid App class.
        ImportError: If the app module cannot be imported.
        Exception: If app creation fails.

    Examples:
        Create a basic app:
        ```python
        app = create_app()
        ```

        Create app with custom config:
        ```python
        app = create_app(config="./custom.config.yaml")
        ```

        Create app with development mode:
        ```python
        app = create_app(dev=True)
        ```

        Create app with custom app class:
        ```python
        app = create_app(app_module_str="myproject.app:CustomApp")
        ```
    """
    # Determine the app class to use
    if app_module_str:
        try:
            app_class = import_from_string(app_module_str)
            if not isclass(app_class) or not issubclass(app_class, App):
                raise ValueError(f"'{app_module_str}' is not a valid App class")
        except Exception as e:
            logger.error(f"Error importing app class '{app_module_str}': {e}")
            raise
    else:
        app_class = App

    # Build app kwargs from provided arguments
    app_kwargs: dict[str, Any] = {}

    if config is not None:
        app_kwargs["config"] = config

    if extension_dirs is not None:
        app_kwargs["extension_dir"] = extension_dirs
    else:
        # Default to ./extensions directory if it exists
        default_extension_dir = Path.cwd() / "extensions"
        if default_extension_dir.exists():
            app_kwargs["extension_dir"] = str(default_extension_dir)

    if dev:
        app_kwargs["dev_mode"] = True

    try:
        logger.info(f"Creating App ({app_class.__name__}) with arguments: {app_kwargs}")
        app = app_class(**app_kwargs)
        return app
    except Exception as e:
        logger.error(f"Error creating app instance: {e}")
        raise
