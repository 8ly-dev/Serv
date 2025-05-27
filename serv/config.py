import importlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, TypeVar

import yaml

logger = logging.getLogger(__name__)

# Default config file name
DEFAULT_CONFIG_FILE = "serv.config.yaml"

T = TypeVar("T")
ImportCallable = Callable[..., Any]


class ExtensionConfig(TypedDict, total=False):
    entry: str
    config: dict[str, Any]


class MiddlewareConfig(TypedDict, total=False):
    entry: str
    config: dict[str, Any]


class ServConfig(TypedDict, total=False):
    site_info: dict[str, Any]
    extensions: list[ExtensionConfig]
    middleware: list[MiddlewareConfig]


class ServConfigError(Exception):
    """Custom exception for configuration errors."""

    pass


def import_from_string(import_str: str) -> Any:
    """Import a class, function, or variable from a module by string.

    This utility function allows dynamic importing of Python objects using
    string notation, which is commonly used in configuration files and
    extension systems.

    Args:
        import_str: String in the format "module.path:symbol" where module.path
            is the Python module path and symbol is the name of the object to
            import from that module.

    Returns:
        The imported object (class, function, variable, etc.).

    Raises:
        ServConfigError: If the import failed due to missing module, missing
            symbol, or other import-related errors.

    Examples:
        Import a class:

        ```python
        # Import the App class from serv.app module
        app_class = import_from_string("serv.app:App")
        app = app_class()
        ```

        Import a function:

        ```python
        # Import a specific function
        handler = import_from_string("myapp.handlers:user_handler")
        ```

        Import a nested attribute:

        ```python
        # Import a nested class or attribute
        validator = import_from_string("myapp.validators:UserValidator.email_validator")
        ```

        Common usage in extension configuration:

        ```python
        # In extension.yaml:
        # entry_points:
        #   main: "myapp.extensions.auth:AuthExtension"

        extension_class = import_from_string("myapp.extensions.auth:AuthExtension")
        extension_instance = extension_class()
        ```

    Note:
        The import string format follows the pattern used by many Python
        frameworks and tools. The colon (:) separates the module path from
        the symbol name within that module.
    """
    if ":" not in import_str:
        raise ServConfigError(
            f"Invalid import string format '{import_str}'. Expected 'module.path:symbol'."
        )

    module_path, object_path = import_str.split(":", 1)

    try:
        module = importlib.import_module(module_path)

        # Handle nested attributes
        target = module
        for part in object_path.split("."):
            target = getattr(target, part)

        return target
    except (ImportError, AttributeError) as e:
        raise ServConfigError(f"Failed to import '{import_str}': {str(e)}") from e


def import_module_from_string(module_path: str) -> Any:
    """
    Import a module by string.

    Args:
        module_path: String representing the module path (e.g., "serv.app")

    Returns:
        The imported module

    Raises:
        ServConfigError: If the import failed.
    """
    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise ServConfigError(
            f"Failed to import module '{module_path}': {str(e)}"
        ) from e


def load_raw_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load a configuration file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Dictionary containing the configuration.

    Raises:
        ServConfigError: If the configuration file could not be loaded.
    """
    try:
        config_path_obj = Path(config_path)
        if not config_path_obj.exists():
            return {}

        with open(config_path_obj) as f:
            config = yaml.safe_load(f)

        if config is None:  # Empty file
            config = {}

        if not isinstance(config, dict):
            raise ServConfigError(
                f"Invalid configuration format in {config_path}. Expected a dictionary."
            )

        return config
    except Exception as e:
        if isinstance(e, ServConfigError):
            raise
        raise ServConfigError(
            f"Error loading configuration from {config_path}: {str(e)}"
        ) from e
