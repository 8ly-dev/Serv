from typing import Annotated

from bevy import auto_inject, injectable
from bevy.registries import Registry
from starlette.requests import Request

from serving.response import ServResponse
from serving.session import InMemorySessionProvider, Session, SessionProvider
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
    cred = DummyCredentialProvider()
    provider = InMemorySessionProvider(credential_provider=cred)

    token = provider.create_session()
    assert token.startswith("tok-")

    provider.update_session(token, {"a": 1, "b": None})
    data = provider.get_session(token)
    assert data == {"a": 1, "b": None}

    provider.invalidate_session(token)
    assert provider.get_session(token) is None


def test_session_load_save_invalidate_sets_cookie_and_persists():
    registry = Registry()
    handle_session_types.register_hook(registry)
    container = registry.create_container()

    # Request + response lifecycle objects
    container.add(ServResponse())
    request = make_request_with_cookies()  # no cookie -> new session
    container.add(Request, request)

    # Provider dependency
    provider = InMemorySessionProvider(credential_provider=DummyCredentialProvider())
    container.add(SessionProvider, provider)

    session = container.call(Session.load_session)
    assert isinstance(session, Session)
    assert session.token

    # Cookie should be set on the response
    set_cookie_header = container.get(ServResponse).headers.get("Set-Cookie", "")
    assert Session.cookie_name in set_cookie_header
    assert session.token in set_cookie_header

    # Persist data, including None values
    session["user_id"] = "u123"
    session["maybe_none"] = None
    session.save()
    assert provider.get_session(session.token) == {"user_id": "u123", "maybe_none": None}

    # Invalidate clears provider storage
    session.invalidate()
    assert provider.get_session(session.token) is None


def test_session_param_injector_uses_membership_and_defaults():
    registry = Registry()
    handle_session_types.register_hook(registry)
    handle_session_param_types.register_hook(registry)
    container = registry.create_container()

    # Request + response lifecycle
    container.add(ServResponse())
    request = make_request_with_cookies()  # will create a new session
    container.add(Request, request)

    # Provider dependency
    provider = InMemorySessionProvider(credential_provider=DummyCredentialProvider())
    container.add(SessionProvider, provider)

    # Ensure a session exists and set values
    session = container.call(Session.load_session)
    session["present_key"] = None
    session.save()

    @auto_inject
    @injectable
    def read_params(
        present_key: Annotated[object, SessionParam],
        missing_key: Annotated[str, SessionParam] = "default-value",
    ):
        return present_key, missing_key

    present, missing = container.call(read_params)
    # present_key should be returned as None (exists with None value)
    assert present is None
    # missing_key should fall back to default
    assert missing == "default-value"

