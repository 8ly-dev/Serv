"""Configuration validation utilities."""

import importlib
from typing import Any, Dict, List, Optional, Type

from ..exceptions import ConfigurationError
from ..providers.base import BaseProvider
from .schema import AuthConfig, ExtensionAuthConfig, ProviderConfig


class AuthConfigValidator:
    """Validates authentication configuration."""

    @classmethod
    def validate_config(cls, config: AuthConfig) -> None:
        """Validate complete auth configuration.

        Args:
            config: Authentication configuration to validate

        Raises:
            ConfigurationError: If configuration is invalid
        """
        cls._validate_providers_config(config.providers)
        cls._validate_security_config(config.security)
        cls._validate_development_config(config.development)

    @classmethod
    def validate_extension_config(cls, config: ExtensionAuthConfig) -> None:
        """Validate extension auth configuration.

        Args:
            config: Extension auth configuration to validate

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if config.permissions:
            cls._validate_permissions(config.permissions)

        if config.roles:
            cls._validate_roles(config.roles)

        if config.routes:
            cls._validate_routes(config.routes)

        if config.routers:
            cls._validate_routers(config.routers)

    @classmethod
    def _validate_providers_config(cls, providers: Any) -> None:
        """Validate providers configuration."""
        required_providers = ["credential", "session", "user", "audit", "policy"]

        for provider_name in required_providers:
            provider_config = getattr(providers, provider_name, None)
            if not provider_config:
                raise ConfigurationError(f"Missing required provider: {provider_name}")

            cls._validate_provider_config(provider_name, provider_config)

    @classmethod
    def _validate_provider_config(
        cls, provider_name: str, config: ProviderConfig
    ) -> None:
        """Validate individual provider configuration.

        Args:
            provider_name: Name of the provider type
            config: Provider configuration

        Raises:
            ConfigurationError: If provider configuration is invalid
        """
        # Validate provider specification
        if not config.provider:
            raise ConfigurationError(
                f"{provider_name} provider specification cannot be empty"
            )

        # If it's an import path, validate it can be imported
        if ":" in config.provider:
            cls._validate_provider_import(provider_name, config.provider)
        else:
            # It's a bundled provider name - validate it exists
            cls._validate_bundled_provider(provider_name, config.provider)

        # Validate provider-specific configuration
        cls._validate_provider_specific_config(provider_name, config.config)

    @classmethod
    def _validate_provider_import(cls, provider_name: str, import_path: str) -> None:
        """Validate that a provider import path is valid.

        Args:
            provider_name: Name of the provider type
            import_path: Import path in format module.path:ClassName

        Raises:
            ConfigurationError: If import path is invalid
        """
        try:
            module_path, class_name = import_path.split(":", 1)
        except ValueError as e:
            raise ConfigurationError(
                f"Invalid import path for {provider_name} provider: {import_path}"
            ) from e

        # Try to import the module and get the class
        try:
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
        except ImportError as e:
            raise ConfigurationError(
                f"Cannot import module for {provider_name} provider"
            ) from e
        except AttributeError as e:
            raise ConfigurationError(
                f"Class '{class_name}' not found in module '{module_path}' for {provider_name} provider"
            ) from e

        # Validate that it's a provider class
        if not issubclass(provider_class, BaseProvider):
            raise ConfigurationError(
                f"Class '{class_name}' is not a valid provider (must inherit from BaseProvider)"
            )

    @classmethod
    def _validate_bundled_provider(cls, provider_name: str, provider_type: str) -> None:
        """Validate that a bundled provider type exists.

        Args:
            provider_name: Name of the provider type
            provider_type: Bundled provider type name

        Raises:
            ConfigurationError: If bundled provider doesn't exist
        """
        # Define known bundled providers
        bundled_providers = {
            "credential": ["memory", "database"],
            "session": ["memory", "database"],
            "user": ["memory", "database"],
            "audit": ["memory", "database", "file"],
            "policy": ["rbac", "abac"],
        }

        valid_types = bundled_providers.get(provider_name, [])
        if provider_type not in valid_types:
            raise ConfigurationError(
                f"Unknown {provider_name} provider type: {provider_type}. "
                f"Valid types: {', '.join(valid_types)}"
            )

    @classmethod
    def _validate_provider_specific_config(
        cls, provider_name: str, config: Dict[str, Any]
    ) -> None:
        """Validate provider-specific configuration.

        Args:
            provider_name: Name of the provider type
            config: Provider configuration dictionary
        """
        # Provider-specific validation rules
        if provider_name == "credential":
            cls._validate_credential_config(config)
        elif provider_name == "session":
            cls._validate_session_config(config)
        elif provider_name == "user":
            cls._validate_user_config(config)
        elif provider_name == "audit":
            cls._validate_audit_config(config)
        elif provider_name == "policy":
            cls._validate_policy_config(config)

    @classmethod
    def _validate_credential_config(cls, config: Dict[str, Any]) -> None:
        """Validate credential provider configuration."""
        # Validate password policy if present
        if "password_policy" in config:
            policy = config["password_policy"]
            if "min_length" in policy:
                min_length = policy["min_length"]
                if not isinstance(min_length, int) or min_length < 1:
                    raise ConfigurationError(
                        "password_policy.min_length must be a positive integer"
                    )

            if "max_age_days" in policy:
                max_age = policy["max_age_days"]
                if not isinstance(max_age, int) or max_age < 1:
                    raise ConfigurationError(
                        "password_policy.max_age_days must be a positive integer"
                    )

        # Validate token settings if present
        if "token_settings" in config:
            token_settings = config["token_settings"]
            if "algorithm" in token_settings:
                algorithm = token_settings["algorithm"]
                valid_algorithms = [
                    "HS256",
                    "HS384",
                    "HS512",
                    "RS256",
                    "RS384",
                    "RS512",
                ]
                if algorithm not in valid_algorithms:
                    raise ConfigurationError(f"Invalid token algorithm: {algorithm}")

    @classmethod
    def _validate_session_config(cls, config: Dict[str, Any]) -> None:
        """Validate session provider configuration."""
        if "concurrent_sessions" in config:
            concurrent_sessions = config["concurrent_sessions"]
            if not isinstance(concurrent_sessions, int) or concurrent_sessions < 1:
                raise ConfigurationError(
                    "concurrent_sessions must be a positive integer"
                )

        if "cleanup_interval" in config:
            # Validate duration format (simple validation)
            interval = config["cleanup_interval"]
            if not isinstance(interval, str) or not any(
                interval.endswith(unit) for unit in ["s", "m", "h", "d"]
            ):
                raise ConfigurationError(
                    "cleanup_interval must be a duration string (e.g., '1h', '30m')"
                )

    @classmethod
    def _validate_user_config(cls, config: Dict[str, Any]) -> None:
        """Validate user provider configuration."""
        if "default_roles" in config:
            default_roles = config["default_roles"]
            if not isinstance(default_roles, list):
                raise ConfigurationError("default_roles must be a list")

            for role in default_roles:
                if not isinstance(role, str):
                    raise ConfigurationError("All default roles must be strings")

    @classmethod
    def _validate_audit_config(cls, config: Dict[str, Any]) -> None:
        """Validate audit provider configuration."""
        if "retention_days" in config:
            retention = config["retention_days"]
            if not isinstance(retention, int) or retention < 1:
                raise ConfigurationError("retention_days must be a positive integer")

        if "encryption_enabled" in config and config["encryption_enabled"]:
            if "encryption_key" not in config:
                raise ConfigurationError(
                    "encryption_key is required when encryption_enabled is true"
                )

    @classmethod
    def _validate_policy_config(cls, config: Dict[str, Any]) -> None:
        """Validate policy provider configuration."""
        if "default_policy" in config:
            default_policy = config["default_policy"]
            valid_policies = ["allow", "deny"]
            if default_policy not in valid_policies:
                raise ConfigurationError(
                    f"default_policy must be one of: {', '.join(valid_policies)}"
                )

    @classmethod
    def _validate_security_config(cls, security: Any) -> None:
        """Validate security configuration."""
        # Validate security headers
        if security.headers:
            headers = security.headers
            if headers.x_frame_options:
                valid_values = ["DENY", "SAMEORIGIN"]
                if headers.x_frame_options not in valid_values:
                    raise ConfigurationError(
                        f"x_frame_options must be one of: {', '.join(valid_values)}"
                    )

    @classmethod
    def _validate_development_config(cls, development: Any) -> None:
        """Validate development configuration."""
        if development.test_users:
            for i, user in enumerate(development.test_users):
                if not user.username:
                    raise ConfigurationError(f"test_users[{i}] must have a username")
                if not user.password:
                    raise ConfigurationError(f"test_users[{i}] must have a password")

    @classmethod
    def _validate_permissions(cls, permissions: List[Any]) -> None:
        """Validate permission definitions."""
        permission_names = set()

        for i, perm in enumerate(permissions):
            if not perm.permission:
                raise ConfigurationError(
                    f"permissions[{i}] must have a permission name"
                )

            if perm.permission in permission_names:
                raise ConfigurationError(
                    f"Duplicate permission name: {perm.permission}"
                )

            permission_names.add(perm.permission)

    @classmethod
    def _validate_roles(cls, roles: List[Any]) -> None:
        """Validate role definitions."""
        role_names = set()

        for i, role in enumerate(roles):
            if not role.name:
                raise ConfigurationError(f"roles[{i}] must have a name")

            if role.name in role_names:
                raise ConfigurationError(f"Duplicate role name: {role.name}")

            role_names.add(role.name)

    @classmethod
    def _validate_routes(cls, routes: List[Any]) -> None:
        """Validate route configurations."""
        for i, route in enumerate(routes):
            if not route.path:
                raise ConfigurationError(f"routes[{i}] must have a path")

            if route.methods:
                valid_methods = [
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "HEAD",
                    "OPTIONS",
                    "*",
                ]
                for method in route.methods:
                    if method not in valid_methods:
                        raise ConfigurationError(
                            f"Invalid HTTP method in routes[{i}]: {method}"
                        )

    @classmethod
    def _validate_routers(cls, routers: List[Any]) -> None:
        """Validate router configurations."""
        router_names = set()

        for i, router in enumerate(routers):
            if not router.name:
                raise ConfigurationError(f"routers[{i}] must have a name")

            if router.name in router_names:
                raise ConfigurationError(f"Duplicate router name: {router.name}")

            router_names.add(router.name)
