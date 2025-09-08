import importlib
import hmac
import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from bevy import Inject, auto_inject, injectable

from serving.config import ConfigModel


class AuthConfigurationError(Exception):
    """Raised when authentication is not configured correctly."""
    def __init__(self, message: str, config_path: Path | None = None):
        super().__init__(message)
        if config_path:
            self.set_config_path(config_path)

    def set_config_path(self, config_path: Path | str):
        self.add_note(f"Configuration file: {config_path}")



@runtime_checkable
class CredentialProvider(Protocol):
    """Protocol for credential providers."""
    def has_credentials(self, permissions: set[str]) -> bool:
        """Check if the authenticated user or client has the specified permissions.

        Args:
            permissions: Permissions to check for

        Returns:
            bool: True if the user has the specified permissions, False otherwise
        """
        ...

    def generate_csrf_token(self) -> str:
        """Generate a CSRF token for form rendering."""
        ...

    def validate_csrf_token(self, token: str) -> bool:
        """Validate a CSRF token provided in a request."""
        ...


@dataclass
class AuthConfig(ConfigModel, model_key="auth"):
    """Configuration for authentication."""
    credential_provider: type[CredentialProvider]
    csrf_secret: str | None = None

    @classmethod
    def from_dict(cls, config: dict) -> "AuthConfig":
        if "credential_provider" not in config:
            raise AuthConfigurationError(
                "Authentication is not correctly configured, missing 'credential_provider' key"
            )
        try:
            import_path, attr = config["credential_provider"].split(":", 1)
            module = importlib.import_module(import_path)
        except ImportError as e:
            raise AuthConfigurationError(
                f"Failed to import credential provider '{config['credential_provider']}'"
            ) from e

        try:
            credential_provider = getattr(module, attr)
        except AttributeError as e:
            raise AuthConfigurationError(
                f"The module '{module.__file__}' does not have the credential provider '{attr}'"
            ) from e

        return cls(
            credential_provider=credential_provider,
            csrf_secret=config.get("csrf_secret"),
        )


@auto_inject
@injectable
class HMACCredentialProvider:
    """Simple HMAC-based credential provider with CSRF support."""

    def __init__(self, config: Inject[AuthConfig]):
        if not config.csrf_secret:
            raise AuthConfigurationError("CSRF secret not configured")
        self._secret = config.csrf_secret.encode()

    def has_credentials(self, permissions: set[str]) -> bool:  # pragma: no cover - example implementation
        return True

    def generate_csrf_token(self) -> str:
        token = secrets.token_urlsafe(32)
        signature = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        return f"{token}.{signature}"

    def validate_csrf_token(self, token: str) -> bool:
        try:
            raw, signature = token.rsplit(".", 1)
        except ValueError:
            return False
        expected = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
