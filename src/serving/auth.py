import importlib
import hmac
import hashlib
import secrets
from dataclasses import dataclass
import time
from pathlib import Path
from typing import Protocol, runtime_checkable, Any

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

    def create_session_token(self) -> str:
        """Generate a new secure session token."""
        ...

    def validate_session_token(self, token: str) -> bool:
        """Validate a session token."""
        ...


@dataclass
class AuthConfig(ConfigModel, model_key="auth"):
    """Configuration for authentication.

    - credential_provider: Provider class to instantiate
    - config: Provider-specific configuration passed as keyword args on instantiation
    """
    credential_provider: type[CredentialProvider]
    config: dict[str, Any] | None = None

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
            config=config.get("config"),
        )


@auto_inject
@injectable
class HMACCredentialProvider:
    """Simple HMAC-based credential provider with CSRF support."""

    def __init__(self, *, csrf_secret: str):
        if not csrf_secret:
            raise AuthConfigurationError("CSRF secret not configured")
        self._secret = csrf_secret.encode()

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

    # Session tokens use the same HMAC signing strategy as CSRF tokens
    def create_session_token(self) -> str:
        token = secrets.token_urlsafe(32)
        signature = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        return f"{token}.{signature}"

    def validate_session_token(self, token: str) -> bool:
        try:
            raw, signature = token.rsplit(".", 1)
        except ValueError:
            return False
        expected = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class TimedHMACCredentialProvider:
    """HMAC-based CSRF provider with embedded timestamp and expiry.

    Token format (URL-safe):
        nonce.timestamp.signature

    - nonce: URL-safe random string (no '.')
    - timestamp: Unix epoch seconds (int)
    - signature: HMAC-SHA256 over "nonce.timestamp" using the configured secret

    Validation checks:
    - Signature must match
    - Token must not be expired based on configured TTL
    """

    @auto_inject
    @injectable
    def __init__(self, *, csrf_secret: str, csrf_ttl_seconds: int | None = 3600):
        if not csrf_secret:
            raise AuthConfigurationError("CSRF secret not configured")
        self._secret = csrf_secret.encode()
        # Default to 1 hour if not provided
        self._ttl = int(csrf_ttl_seconds or 3600)

    def has_credentials(self, permissions: set[str]) -> bool:  # pragma: no cover - example implementation
        return True

    def generate_csrf_token(self) -> str:
        # URL-safe nonce; '.' is not produced by token_urlsafe
        nonce = secrets.token_urlsafe(32)
        ts = str(int(time.time()))
        raw = f"{nonce}.{ts}"
        sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def validate_csrf_token(self, token: str) -> bool:
        try:
            nonce, ts_str, sig = token.split(".", 3)
        except ValueError:
            return False

        # Recompute signature
        raw = f"{nonce}.{ts_str}"
        expected_sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return False

        # Check expiry
        try:
            ts = int(ts_str)
        except ValueError:
            return False

        now = int(time.time())
        if ts > now:
            # Future timestamp is invalid
            return False

        return (now - ts) <= self._ttl

    # Session tokens include a timestamp and are validated server-side by the session provider
    def create_session_token(self) -> str:
        nonce = secrets.token_urlsafe(32)
        ts = str(int(time.time()))
        raw = f"{nonce}.{ts}"
        sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def validate_session_token(self, token: str) -> bool:
        try:
            nonce, ts_str, sig = token.split(".", 3)
        except ValueError:
            return False

        raw = f"{nonce}.{ts_str}"
        expected_sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return False

        try:
            ts = int(ts_str)
        except ValueError:
            return False

        now = int(time.time())
        if ts > now:
            return False
        return (now - ts) <= self._ttl
