"""Simple config parsing utilities for auth system."""

from typing import Any, Dict, Optional

from pydantic import ValidationError

from ..exceptions import ConfigurationError
from .schema import AuthConfig, ExtensionAuthConfig


def parse_auth_config(auth_config: Dict[str, Any]) -> AuthConfig:
    """Parse and validate auth configuration.
    
    Args:
        auth_config: Auth configuration dictionary (from app's config['auth'])
        
    Returns:
        Validated AuthConfig instance
        
    Raises:
        ConfigurationError: If auth configuration is invalid
    """
    if not auth_config:
        raise ConfigurationError("Auth configuration is empty")
    
    # Validate configuration using Pydantic
    try:
        return AuthConfig(**auth_config)
    except ValidationError as e:
        raise ConfigurationError(f"Invalid auth configuration: {e}")


def parse_extension_auth_config(extension_config: Dict[str, Any]) -> Optional[ExtensionAuthConfig]:
    """Parse extension-specific auth configuration.
    
    Args:
        extension_config: Extension configuration dictionary
        
    Returns:
        ExtensionAuthConfig instance if auth section exists, None otherwise
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    if not extension_config:
        return None
    
    # Extract auth section
    auth_config = extension_config.get("auth")
    if not auth_config:
        return None
    
    # Validate configuration
    try:
        return ExtensionAuthConfig(**auth_config)
    except ValidationError as e:
        raise ConfigurationError(f"Invalid extension auth configuration: {e}")


def merge_extension_configs(
    base_config: AuthConfig, 
    extension_configs: list[ExtensionAuthConfig]
) -> AuthConfig:
    """Merge extension configurations into base auth configuration.
    
    This method combines permissions, roles, and policies from extensions
    into the main auth configuration for validation and use.
    
    Args:
        base_config: Main auth configuration
        extension_configs: List of extension auth configurations
        
    Returns:
        Merged configuration
    """
    # For now, return base config as-is
    # This method will be expanded when we implement extension integration
    return base_config