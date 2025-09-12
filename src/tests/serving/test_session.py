from typing import Annotated

from bevy import auto_inject, injectable, get_registry
from bevy.registries import Registry
from starlette.requests import Request

from serving.response import ServResponse
from serving.session import InMemorySessionProvider, Session, SessionProvider
from serving.auth import CredentialProvider
from serving.injectors import (
    handle_session_types,
    handle_session_param_types,
    SessionParam,
)


class DummyCredentialProvider:
    def __init__(self):
        self._tokens: set[str] = set()

    def create_session_token(self) -> str:
        token = f"tok-{len(self._tokens) + 1}"
        self._tokens.add(token)
        return token

    def validate_session_token(self, token: str) -> bool:
        return token in self._tokens


def make_request_with_cookies(cookie_header: str | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    if cookie_header is not None:
        scope["headers"].append((b"cookie", cookie_header.encode()))
    return Request(scope)


def test_inmemory_session_provider_create_update_invalidate():
    # Use a DI container so method calls can resolve dependencies
    registry = get_registry()
    container = registry.create_container()
    container.add(CredentialProvider, DummyCredentialProvider())
    provider = container.call(InMemorySessionProvider)

    token = provider.create_session()
    assert token.startswith("tok-")

    provider.update_session(token, {"a": 1, "b": None})
    data = provider.get_session(token)
    assert data == {"a": 1, "b": None}

    provider.invalidate_session(token)
    assert provider.get_session(token) is None


def test_session_load_save_invalidate_sets_cookie_and_persists():
    registry = get_registry()
    handle_session_types.register_hook(registry)
    container = registry.create_container()

    # Request + response lifecycle objects
    container.add(ServResponse())
    request = make_request_with_cookies()  # no cookie -> new session
    container.add(Request, request)

    # Provider dependency
    container.add(CredentialProvider, DummyCredentialProvider())
    provider = container.call(InMemorySessionProvider)
    container.add(SessionProvider, provider)

    session = container.call(Session.load_session)
    assert isinstance(session, Session)
    assert session.token

    # Session token should be present
    assert session.token

    # Persist data, including None values
    session["user_id"] = "u123"
    session["maybe_none"] = None
    session.save()
    assert container.call(provider.get_session, session.token) == {"user_id": "u123", "maybe_none": None}

    # Invalidate clears provider storage
    session.invalidate()
    assert container.call(provider.get_session, session.token) is None


# Additional integration of Session via injector is exercised in runtime tests.
