from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import pytest
from bevy import Inject, auto_inject, injectable
from bevy.registries import Registry
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from serving.auth import CredentialProvider
from serving.forms import CSRFProtection, Form, MissingCSRFTokenError
from serving.injectors import handle_form_types


class DummyCredentialProvider:
    def has_credentials(self, permissions: set[str]) -> bool:
        return True

    def generate_csrf_token(self) -> str:
        return "token"

    def validate_csrf_token(self, token: str) -> bool:
        return token == "token"


def setup_container(tmp_path: Path):
    registry = Registry()
    container = registry.create_container()
    templates = Jinja2Templates(directory=tmp_path)
    container.add(templates)
    container.add(CredentialProvider, DummyCredentialProvider())
    handle_form_types.register_hook(registry)
    return container


def test_form_render_includes_csrf_token(tmp_path):
    (tmp_path / "login.html").write_text("{{ form.username }} {{ csrf() }}")
    container = setup_container(tmp_path)

    @dataclass
    class Login(Form, template="login.html"):
        username: str

    with container.branch():
        result = Login(username="alice").render()

    assert "alice" in result
    assert '<input type="hidden" name="csrf_token" value="token">' in result


def test_form_render_without_csrf_when_disabled(tmp_path):
    (tmp_path / "login.html").write_text("no token here")
    container = setup_container(tmp_path)

    @dataclass
    class NoCSRF(Form, template="login.html", csrf=CSRFProtection.Disabled):
        pass

    with container.branch():
        result = NoCSRF().render()

    assert "csrf_token" not in result


@pytest.mark.asyncio
async def test_from_request_validates_csrf(tmp_path):
    (tmp_path / "login.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Login(Form, template="login.html"):
        username: str

    body = urlencode({"username": "alice", "csrf_token": "token"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch():
        form = await Login.from_request(request)

    assert form.username == "alice"


@pytest.mark.asyncio
async def test_from_request_invalid_csrf(tmp_path):
    (tmp_path / "login.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Login(Form, template="login.html"):
        username: str

    body = urlencode({"username": "alice", "csrf_token": "bad"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch():
        with pytest.raises(ValueError):
            await Login.from_request(request)


def test_form_field_name_conflicts(tmp_path):
    (tmp_path / "conflict.html").write_text("{{ form.template }} {{ form.csrf }} {{ csrf() }}")
    container = setup_container(tmp_path)

    @dataclass
    class Conflict(Form, template="conflict.html"):
        template: str
        csrf: str

    with container.branch():
        result = Conflict(template="foo", csrf="bar").render()

    assert "foo" in result
    assert "bar" in result
def test_form_render_raises_when_csrf_missing(tmp_path):
    (tmp_path / "login.html").write_text("{{ form.username }}")
    container = setup_container(tmp_path)

    @dataclass
    class Login(Form, template="login.html"):
        username: str

    with container.branch():
        with pytest.raises(MissingCSRFTokenError):
            Login(username="alice").render()


def test_form_injection_uses_cached_instance(tmp_path):
    (tmp_path / "simple.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Simple(Form, template="simple.html", csrf=CSRFProtection.Disabled):
        name: str

    body = urlencode({"name": "alice"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch() as c:
        c.add(Request, request)

        @auto_inject
        @injectable
        def use_form(form1: Inject[Simple], form2: Inject[Simple]):
            return form1, form2

        form1, form2 = c.call(use_form)

    assert form1.name == "alice"
    assert form1 is form2


@pytest.mark.asyncio
async def test_form_injection_invalid_csrf_via_injector(tmp_path):
    (tmp_path / "login.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Login(Form, template="login.html"):
        username: str

    body = urlencode({"username": "alice", "csrf_token": "bad"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch() as c:
        c.add(Request, request)

        @auto_inject
        @injectable
        def use_form(form: Inject[Login]):
            return form

        with pytest.raises(ValueError):
            # Injection should invoke the async hook which validates CSRF
            c.call(use_form)


@pytest.mark.asyncio
async def test_form_injection_into_async_function(tmp_path):
    (tmp_path / "simple.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Simple(Form, template="simple.html", csrf=CSRFProtection.Disabled):
        name: str

    body = urlencode({"name": "bob"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch() as c:
        c.add(Request, request)

        @auto_inject
        @injectable
        async def use_form_async(form1: Inject[Simple], form2: Inject[Simple]):
            return form1, form2

        form1, form2 = await c.call(use_form_async)

    assert form1.name == "bob"
    assert form1 is form2


def test_form_injection_cached_across_calls_in_same_branch(tmp_path):
    (tmp_path / "simple.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Simple(Form, template="simple.html", csrf=CSRFProtection.Disabled):
        name: str

    body = urlencode({"name": "carol"}).encode()
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive=receive)

    with container.branch() as c:
        c.add(Request, request)

        @auto_inject
        @injectable
        def get_form(form: Inject[Simple]):
            return form

        form_a = c.call(get_form)
        form_b = c.call(get_form)

    assert form_a.name == "carol"
    assert form_a is form_b


def test_form_injection_new_instance_per_branch(tmp_path):
    (tmp_path / "simple.html").write_text("")
    container = setup_container(tmp_path)

    @dataclass
    class Simple(Form, template="simple.html", csrf=CSRFProtection.Disabled):
        name: str

    def make_request(value: str):
        body = urlencode({"name": value}).encode()
        headers = [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode()),
        ]
        scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(scope, receive=receive)

    @auto_inject
    @injectable
    def get_form(form: Inject[Simple]):
        return form

    with container.branch() as c1:
        c1.add(Request, make_request("one"))
        form1 = c1.call(get_form)

    with container.branch() as c2:
        c2.add(Request, make_request("two"))
        form2 = c2.call(get_form)

    assert form1.name == "one"
    assert form2.name == "two"
    assert form1 is not form2
