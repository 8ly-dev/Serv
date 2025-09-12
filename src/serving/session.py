from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any, ClassVar, Optional

from bevy import Inject, auto_inject, injectable
from starlette.requests import Request

from serving.auth import CredentialProvider
from serving.config import ConfigModel
from serving.response import set_cookie, delete_cookie, ServResponse
from bevy import get_container


@runtime_checkable
class SessionProvider(Protocol):
    """Protocol for session providers."""

    def create_session(self) -> str:
        """Create a new session and return its token."""
        ...

    def update_session(self, token: str, values: dict[str, Any]) -> None:
        """Update the session data with provided values."""
        ...

    def invalidate_session(self, token: str) -> None:
        """Invalidate the session and remove its data."""
        ...

    def get_session(self, token: str) -> dict[str, Any] | None:
        """Retrieve the current session data for the token, or None if not found."""
        ...


@dataclass
class SessionConfig(ConfigModel, model_key="session"):
    """Configuration for sessions.

    - session_provider: Provider class to instantiate
    - config: Provider-specific configuration passed as keyword args on instantiation
    - session_type: Concrete Session class to use for request-bound session access
    """

    session_provider: type[SessionProvider]
    config: dict[str, Any] | None = None
    session_type: type["Session"] | None = None

    @classmethod
    def from_dict(cls, config: dict) -> "SessionConfig":
        # Resolve provider
        if "session_provider" not in config:
            raise ValueError("Session is not correctly configured, missing 'session_provider' key")

        import importlib
        try:
            import_path, attr = config["session_provider"].split(":", 1)
            module = importlib.import_module(import_path)
            session_provider = getattr(module, attr)
        except Exception as e:
            raise ValueError(f"Failed to import session provider '{config.get('session_provider')}'") from e

        # Resolve session type (optional)
        session_type = None
        if st := config.get("session_type"):
            try:
                import_path, attr = st.split(":", 1)
                module = importlib.import_module(import_path)
                session_type = getattr(module, attr)
            except Exception as e:
                raise ValueError(f"Failed to import session type '{st}'") from e

        return cls(
            session_provider=session_provider,
            config=config.get("config"),
            session_type=session_type,
        )


class InMemorySessionProvider:
    """Simple in-memory session provider for development and tests."""

    def __init__(self, credential_provider: Inject[CredentialProvider]):
        self._cred = credential_provider
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self) -> str:
        token = self._cred.create_session_token()
        self._sessions[token] = {}
        return token

    def update_session(self, token: str, values: dict[str, Any]) -> None:
        if token in self._sessions:
            self._sessions.setdefault(token, {}).update(values)

    def invalidate_session(self, token: str) -> None:
        self._sessions.pop(token, None)

    def get_session(self, token: str) -> dict[str, Any] | None:
        # Validate the token format/signature if the provider supports it
        validator = getattr(self._cred, "validate_session_token", None)
        if callable(validator) and not validator(token):
            return None
        return self._sessions.get(token)


class Session:
    """Default session mapping with cookie-based token storage.

    Subclass to customize behavior; override `cookie_name` or extend methods.
    """

    cookie_name: ClassVar[str] = "serving_session"

    def __init__(self, token: str, data: dict[str, Any], provider: SessionProvider):
        self._token = token
        self._data = dict(data)
        self._provider = provider

    # Mapping dunders
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    @property
    def token(self) -> str:
        return self._token

    def save(self) -> None:
        """Persist current state to the provider."""
        self._provider.update_session(self._token, self._data)

    def invalidate(self) -> None:
        """Invalidate session and clear client cookie."""
        self._provider.invalidate_session(self._token)
        # Try to clear cookie via response; fall back silently if not in a request context
        try:
            # Avoid ensure_request_lifecycle wrapper to support test contexts
            resp = get_container().get(ServResponse)
            resp.headers['Set-Cookie'] = f"{self.cookie_name}=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
        except Exception:
            try:
                delete_cookie(self.cookie_name)
            except Exception:
                pass
        self._data.clear()

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Get a value from the session with an optional default."""
        return self._data.get(key, default)

    @classmethod
    @auto_inject
    @injectable
    def load_session[
        T: "Session"
    ](
        cls: type[T],
        request: Inject[Request],
        provider: Inject[SessionProvider],
    ) -> T:
        """Load or create the session for the current request.

        - Reads a session token from cookie; if missing or not found, creates a new session
        - Sets the cookie for new sessions
        """
        token: Optional[str] = request.cookies.get(cls.cookie_name)
        data: dict[str, Any] | None = None

        if token:
            data = provider.get_session(token)

        if not token or data is None:
            token = provider.create_session()
            # Try to set cookie via response; fall back silently if not in a request context
            try:
                resp = get_container().get(ServResponse)
                resp.headers['Set-Cookie'] = f"{cls.cookie_name}={token}"
            except Exception:
                try:
                    set_cookie(cls.cookie_name, token)
                except Exception:
                    pass
            data = {}

        return cls(token, data, provider)
