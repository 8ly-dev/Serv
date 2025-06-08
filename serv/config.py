import importlib
import logging
import os
import re
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


class DatabaseConfig(TypedDict, total=False):
    provider: str
    qualifier: str | None
    connection_string: str
    settings: dict[str, Any]


class AuthProviderConfig(TypedDict, total=False):
    type: str
    config: dict[str, Any]


class AuthConfig(TypedDict, total=False):
    providers: list[AuthProviderConfig]
    storage: dict[str, Any]
    rate_limiting: dict[str, str | int]
    audit: dict[str, Any]
    policies: dict[str, Any]
    security: dict[str, Any]


class ServConfig(TypedDict, total=False):
    site_info: dict[str, Any]
    extensions: list[ExtensionConfig]
    middleware: list[MiddlewareConfig]
    databases: dict[str, DatabaseConfig]
    auth: AuthConfig


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


def _substitute_env_vars(config: dict[str, Any]) -> dict[str, Any]:
    """
    Substitute environment variables in configuration values.
    
    Supports ${VAR_NAME} syntax for environment variable substitution.
    This is critical for secure configuration management, especially
    for authentication secrets.
    
    Security considerations:
    - Environment variables should be used for sensitive data
    - Missing required environment variables should cause startup failure
    - Environment variable names should be validated
    
    Args:
        config: Configuration dictionary with potential environment variables
        
    Returns:
        Configuration with environment variables substituted
        
    Raises:
        ServConfigError: If required environment variable is missing
    """
    def substitute_value(value: Any) -> Any:
        if isinstance(value, str):
            # Find all ${VAR_NAME} patterns
            env_pattern = re.compile(r'\$\{([^}]+)\}')
            
            def replace_env_var(match):
                env_var = match.group(1)
                env_value = os.getenv(env_var)
                
                if env_value is None:
                    raise ServConfigError(
                        f"Required environment variable '{env_var}' is not set"
                    )
                
                return env_value
            
            return env_pattern.sub(replace_env_var, value)
        
        elif isinstance(value, dict):
            return {k: substitute_value(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [substitute_value(item) for item in value]
        
        else:
            return value
    
    return substitute_value(config)


def validate_auth_config(auth_config: dict[str, Any]) -> None:
    """
    Validate authentication configuration for security.
    
    Security considerations:
    - Secret keys must meet minimum security requirements
    - Rate limiting must be properly configured
    - Storage backend must be specified
    - Timing protection settings must be reasonable
    
    Args:
        auth_config: Authentication configuration to validate
        
    Raises:
        ServConfigError: If configuration is insecure or invalid
    """
    if not auth_config:
        return  # Auth config is optional
    
    # Validate providers
    providers = auth_config.get("providers", [])
    if providers:
        for i, provider in enumerate(providers):
            if not isinstance(provider, dict):
                raise ServConfigError(f"Auth provider {i} must be a dictionary")
            
            if "type" not in provider:
                raise ServConfigError(f"Auth provider {i} missing required 'type' field")
            
            provider_type = provider["type"]
            provider_config = provider.get("config", {})
            
            # Validate JWT provider security
            if provider_type == "jwt":
                secret_key = provider_config.get("secret_key")
                if secret_key and len(secret_key) < 32:
                    raise ServConfigError(
                        "JWT secret_key must be at least 32 characters for security"
                    )
                
                algorithm = provider_config.get("algorithm", "HS256")
                if algorithm not in ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]:
                    raise ServConfigError(f"Unsupported JWT algorithm: {algorithm}")
    
    # Validate storage configuration
    storage = auth_config.get("storage")
    if storage is not None and "backend" not in storage:
        raise ServConfigError("Auth storage configuration missing required 'backend' field")
    
    # Validate rate limiting configuration
    rate_limiting = auth_config.get("rate_limiting", {})
    for action, limit in rate_limiting.items():
        if isinstance(limit, str):
            try:
                _parse_rate_limit_string(limit)
            except ValueError as e:
                raise ServConfigError(f"Invalid rate limit for '{action}': {e}")
    
    # Validate security settings
    security = auth_config.get("security", {})
    timing_protection = security.get("timing_protection", {})
    if timing_protection.get("enabled"):
        min_auth_time = timing_protection.get("minimum_auth_time", 2.0)
        if min_auth_time < 0.1:
            raise ServConfigError(
                "minimum_auth_time should be at least 0.1 seconds for security"
            )


def _parse_rate_limit_string(limit_str: str) -> dict[str, Any]:
    """
    Parse rate limit string like "10/min" or "100/hour".
    
    Args:
        limit_str: Limit string to parse
        
    Returns:
        Dictionary with limit and window information
        
    Raises:
        ValueError: If limit string is invalid
    """
    try:
        count_str, window_str = limit_str.split("/", 1)
        count = int(count_str)
        
        window_map = {
            "sec": 1,
            "second": 1,
            "min": 60,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }
        
        window_seconds = window_map.get(window_str.lower())
        if window_seconds is None:
            raise ValueError(f"Invalid time window: {window_str}")
        
        if count <= 0:
            raise ValueError("Rate limit count must be positive")
        
        return {
            "limit": count,
            "window_seconds": window_seconds,
            "window_name": window_str.lower()
        }
        
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid rate limit format '{limit_str}': {e}")


def load_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load and process configuration file with security validation.
    
    This function loads the raw configuration, substitutes environment
    variables, and validates security settings for authentication.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Processed and validated configuration dictionary
        
    Raises:
        ServConfigError: If configuration is invalid or insecure
    """
    # Load raw configuration
    config = load_raw_config(config_path)
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    # Validate auth configuration if present
    if "auth" in config:
        validate_auth_config(config["auth"])
    
    return config
