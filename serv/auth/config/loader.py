"""Configuration loading and processing."""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from ..exceptions import ConfigurationError
from .schema import AuthConfig, ExtensionAuthConfig


class AuthConfigLoader:
    """Loads and validates authentication configuration."""

    # Pattern for environment variable substitution
    ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

    @classmethod
    def load_auth_config(cls, config_path: Path) -> AuthConfig:
        """Load authentication configuration from YAML file.

        Args:
            config_path: Path to the main serv.config.yaml file

        Returns:
            Validated AuthConfig instance

        Raises:
            ConfigurationError: If configuration is invalid or cannot be loaded
        """
        try:
            with open(config_path, "r") as f:
                raw_config = yaml.safe_load(f)
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}")

        if not raw_config:
            raise ConfigurationError("Configuration file is empty")

        # Extract auth section
        auth_config = raw_config.get("auth", {})
        if not auth_config:
            raise ConfigurationError("No 'auth' section found in configuration")

        # Process environment variables
        processed_config = cls._substitute_env_vars(auth_config)

        # Validate configuration
        try:
            return AuthConfig(**processed_config)
        except ValidationError as e:
            raise ConfigurationError(f"Invalid auth configuration: {e}")

    @classmethod
    def load_extension_auth_config(
        cls, extension_yaml: Path
    ) -> Optional[ExtensionAuthConfig]:
        """Load extension-specific auth configuration.

        Args:
            extension_yaml: Path to the extension.yaml file

        Returns:
            ExtensionAuthConfig instance if auth section exists, None otherwise

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            with open(extension_yaml, "r") as f:
                raw_config = yaml.safe_load(f)
        except FileNotFoundError:
            # Extension files are optional
            return None
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in extension file: {e}")

        if not raw_config:
            return None

        # Extract auth section
        auth_config = raw_config.get("auth")
        if not auth_config:
            return None

        # Process environment variables
        processed_config = cls._substitute_env_vars(auth_config)

        # Validate configuration
        try:
            return ExtensionAuthConfig(**processed_config)
        except ValidationError as e:
            raise ConfigurationError(f"Invalid extension auth configuration: {e}")

    @classmethod
    def _substitute_env_vars(cls, config: Any) -> Any:
        """Recursively substitute environment variables in configuration.

        Supports these patterns:
        - ${VAR_NAME} - simple substitution
        - ${VAR_NAME:-default} - substitution with default value
        - ${VAR_NAME:?error message} - required variable with error message

        Args:
            config: Configuration object (dict, list, str, etc.)

        Returns:
            Configuration with environment variables substituted

        Raises:
            ConfigurationError: If required environment variable is missing
        """
        if isinstance(config, dict):
            return {
                key: cls._substitute_env_vars(value) for key, value in config.items()
            }
        elif isinstance(config, list):
            return [cls._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            return cls._substitute_env_var_string(config)
        else:
            return config

    @classmethod
    def _substitute_env_var_string(cls, value: str) -> str:
        """Substitute environment variables in a string value.

        Args:
            value: String that may contain environment variable references

        Returns:
            String with environment variables substituted

        Raises:
            ConfigurationError: If required environment variable is missing
        """

        def replace_var(match):
            var_expr = match.group(1)

            # Handle default value syntax: VAR_NAME:-default
            if ":-" in var_expr:
                var_name, default_value = var_expr.split(":-", 1)
                return os.getenv(var_name, default_value)

            # Handle required variable syntax: VAR_NAME:?error message
            elif ":?" in var_expr:
                var_name, error_msg = var_expr.split(":?", 1)
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ConfigurationError(
                        f"Required environment variable '{var_name}' not set: {error_msg}"
                    )
                return env_value

            # Simple substitution
            else:
                env_value = os.getenv(var_expr)
                if env_value is None:
                    raise ConfigurationError(
                        f"Environment variable '{var_expr}' not set"
                    )
                return env_value

        return cls.ENV_VAR_PATTERN.sub(replace_var, value)

    @classmethod
    def merge_configs(
        cls, base_config: AuthConfig, extension_configs: list[ExtensionAuthConfig]
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

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default configuration file path.

        Returns:
            Path to serv.config.yaml in current directory
        """
        return Path.cwd() / "serv.config.yaml"

    @classmethod
    def validate_config_exists(cls, config_path: Optional[Path] = None) -> Path:
        """Validate that configuration file exists.

        Args:
            config_path: Optional path to config file

        Returns:
            Validated path to configuration file

        Raises:
            ConfigurationError: If configuration file doesn't exist
        """
        if config_path is None:
            config_path = cls.get_default_config_path()

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        if not config_path.is_file():
            raise ConfigurationError(f"Configuration path is not a file: {config_path}")

        return config_path
