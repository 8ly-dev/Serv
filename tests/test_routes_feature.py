from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.extensions import Extension, on
from serv.injectors import Cookie, Header, Query
from serv.routes import (
    Form,
    Jinja2Response,
    JsonResponse,
    Response,
    Route,
    TextResponse,
    handle,
)
from serv.routing import (
    Router,  # For type hinting if needed, actual router comes from event
)
from tests.helpers import create_test_extension_spec

# --- Test-specific Form and Route classes ---


@dataclass
class SimpleForm(Form):
    name: str
    age: int


@dataclass
class AnotherForm(Form):
    item_id: str


class MyCustomException(Exception):
    pass


class ComplexTestRoute(Route):
    @handle.GET
    async def get_handler(self) -> Annotated[str, TextResponse]:
        return "GET request processed"

    @handle.POST
    async def post_simple_form(self, form: SimpleForm) -> Annotated[str, TextResponse]:
        return f"Form processed: Name={form.name}, Age={form.age}"

    @handle.POST
    async def post_another_form(
        self, form: AnotherForm
    ) -> Annotated[str, TextResponse]:
        return f"AnotherForm processed: ItemID={form.item_id}"

    async def handle_custom_error(self, error: MyCustomException) -> Response:
        return TextResponse("Custom error handled", status_code=501)


class CustomErrorRoute(Route):
    @handle.GET
    async def get_handler(self) -> Response:
        raise MyCustomException("Something went wrong!")

    async def handle_custom_error(self, error: MyCustomException) -> Response:
        return TextResponse("Custom error handled", status_code=501)


class UnhandledErrorRoute(Route):
    @handle.GET
    async def get_handler(self) -> Response:
        raise ValueError("This is an unhandled error.")


# --- New Routes for Annotated Response Tests ---


class JsonAnnotatedRoute(Route):
    @handle.GET
    async def get_handler(
        self,
    ) -> Annotated[list[dict[str, Any]], JsonResponse]:
        return [{"id": 1, "name": "Test User"}, {"id": 2, "name": "Another User"}]


class TextAnnotatedRoute(Route):
    @handle.GET
    async def get_handler(self) -> Annotated[str, TextResponse]:
        return "Hello from annotated text!"


class RawDictRoute(Route):  # For testing error case
    @handle.GET
    async def get_handler(self) -> dict[str, str]:
        return {"message": "This is a raw dict"}


class RawStringRoute(Route):
    @handle.GET
    async def get_handler(self) -> str:
        return "This is a raw string."


class DirectResponseInstanceRoute(Route):
    @handle.GET
    async def get_handler(self) -> Response:
        return TextResponse("Direct Response instance.", status_code=201)


class JsonAnnotatedCustomStatusRoute(Route):
    @handle.GET
    async def get_handler(
        self,
    ) -> Annotated[dict[str, str], JsonResponse]:
        return {"custom_status_test": "data"}


class Jinja2TestResponse(Jinja2Response):
    @staticmethod
    def _get_template_locations(_):
        return Path(__file__).parent / "templates"


# New route for Jinja2 tuple return test
class JinjaTupleReturnRoute(Route):
    @handle.GET
    async def get_handler(
        self,
    ) -> Annotated[tuple[str, dict[str, str]], Jinja2TestResponse]:
        return ("jinja_tuple_test.html", {"greeting": "Hello from Jinja via tuple"})


# --- Routes for testing parameter injection ---


class ParameterInjectionRoute(Route):
    @handle.GET
    async def get_with_query(
        self, user_id: Annotated[str, Query("id")]
    ) -> Annotated[dict, JsonResponse]:
        return {"user_id": user_id, "source": "query"}

    @handle.GET
    async def get_with_header(
        self, auth_token: Annotated[str, Header("Authorization")]
    ) -> Annotated[dict, JsonResponse]:
        return {"auth_token": auth_token, "source": "header"}

    @handle.GET
    async def get_with_cookie(
        self, session_id: Annotated[str, Cookie("session_id")]
    ) -> Annotated[dict, JsonResponse]:
        return {"session_id": session_id, "source": "cookie"}

    @handle.GET
    async def get_with_defaults(
        self,
        optional_param: Annotated[str, Query("optional", default="default_value")],
    ) -> Annotated[dict, JsonResponse]:
        return {"optional_param": optional_param, "source": "query_with_default"}

    @handle.GET
    async def get_multiple_params(
        self,
        user_id: Annotated[str, Query("id")],
        auth_token: Annotated[str, Header("Authorization")],
        session_id: Annotated[str, Cookie("session_id", default="no_session")],
    ) -> Annotated[dict, JsonResponse]:
        return {
            "user_id": user_id,
            "auth_token": auth_token,
            "session_id": session_id,
            "source": "multiple",
        }

    @handle.GET
    async def get_fallback(self) -> Annotated[dict, JsonResponse]:
        return {"message": "fallback handler", "source": "fallback"}


# --- Routes for testing signature matching and handler scoring ---


class MultipleGetHandlersRoute(Route):
    """Route with multiple GET handlers to test signature matching"""

    @handle.GET
    async def get_with_user_id(
        self, user_id: Annotated[str, Query("user_id")]
    ) -> Annotated[dict, JsonResponse]:
        return {"handler": "user_id", "user_id": user_id}

    @handle.GET
    async def get_with_category(
        self, category: Annotated[str, Query("category")]
    ) -> Annotated[dict, JsonResponse]:
        return {"handler": "category", "category": category}

    @handle.GET
    async def get_with_both(
        self,
        user_id: Annotated[str, Query("user_id")],
        category: Annotated[str, Query("category")],
    ) -> Annotated[dict, JsonResponse]:
        return {"handler": "both", "user_id": user_id, "category": category}

    @handle.GET
    async def get_fallback(self) -> Annotated[dict, JsonResponse]:
        return {"handler": "fallback", "message": "no specific parameters"}


class ParameterInjectionFailureRoute(Route):
    """Route to test parameter injection failures"""

    @handle.GET
    async def get_required_missing(
        self, required_param: Annotated[str, Query("required")]
    ) -> Annotated[dict, JsonResponse]:
        return {"required_param": required_param}


class ParameterInjectionWithDefaultRoute(Route):
    """Route to test parameter injection with default values"""

    @handle.GET
    async def get_with_default(
        self, optional_param: Annotated[str, Query("optional", default="default")]
    ) -> Annotated[dict, JsonResponse]:
        return {"optional_param": optional_param}


class HandlerScoringRoute(Route):
    """Route to test handler scoring system"""

    @handle.GET
    async def get_high_score(
        self,
        param1: Annotated[str, Query("param1")],
        param2: Annotated[str, Query("param2")],
    ) -> Annotated[dict, JsonResponse]:
        return {"handler": "high_score", "param1": param1, "param2": param2}

    @handle.GET
    async def get_medium_score(
        self, param1: Annotated[str, Query("param1")]
    ) -> Annotated[dict, JsonResponse]:
        return {"handler": "medium_score", "param1": param1}

    @handle.GET
    async def get_low_score(self) -> Annotated[dict, JsonResponse]:
        return {"handler": "low_score"}


# --- Test Extension for adding Route classes ---


class RouteTestExtension(Extension):
    def __init__(self, path: str, route_class: type[Route]):
        # Set up the plugin spec on the module before calling super().__init__()
        self._extension_spec = create_test_extension_spec(
            name="RouteTestExtension", path=Path(__file__).parent
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self.path = path
        self.route_class = route_class
        self.router_instance_id_at_registration = None
        self.plugin_registered_route = False
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        # Using app.request.begin as it seems to be a point where router_instance is available
        # A dedicated app.startup or app.plugins.loaded event might be cleaner if available.
        router.add_route(self.path, self.route_class)
        self.router_instance_id_at_registration = id(router)
        self.plugin_registered_route = True  # Register only once


# --- Tests ---


@pytest.mark.asyncio
async def test_route_get_method(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    response = await client.get("/test_complex")
    assert response.status_code == 200
    assert response.text == "GET request processed"
    assert plugin.plugin_registered_route  # Ensure plugin logic ran


@pytest.mark.asyncio
async def test_route_post_form_success(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    response = await client.post("/test_complex", data={"name": "Alice", "age": "30"})
    assert response.status_code == 200
    assert response.text == "Form processed: Name=Alice, Age=30"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_post_form_missing_field(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    # This should not match SimpleForm due to missing 'age',
    # and ComplexTestRoute has no generic POST handler.
    # So, it should fall to a 405 or whatever the Route's __call__
    # or the app's default is for no matching form/method handler.
    # The Route.__call__ itself raises HTTPMethodNotAllowedException if no form or method matches.
    response = await client.post("/test_complex", data={"name": "Bob"})
    assert (
        response.status_code == 405
    )  # Expecting MNA as no form matched and no general POST
    # The ComplexTestRoute has handle_method_not_allowed_override
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_post_form_wrong_type(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    # Age is not an int. Should not match SimpleForm.
    response = await client.post(
        "/test_complex", data={"name": "Charlie", "age": "thirty"}
    )
    assert response.status_code == 405
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_another_form_post_method(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    response = await client.post("/test_complex", data={"item_id": "xyz123"})
    assert response.status_code == 200
    assert response.text == "AnotherForm processed: ItemID=xyz123"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_custom_error_handler(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_raiser", CustomErrorRoute)
    app.add_extension(plugin)

    response = await client.get("/test_raiser")
    assert response.status_code == 501
    assert response.text == "Custom error handled"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_unhandled_error(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_unhandled", UnhandledErrorRoute)
    app.add_extension(plugin)

    response = await client.get("/test_unhandled")
    # Expecting a generic 500 error as it's unhandled by the Route itself.
    # The app's default error handler should catch this.
    assert response.status_code == 500
    # The default error handler in app.py might return HTML or plain text.
    # For now, just check status code. If specific text is needed, inspect app's default handler.
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_method_not_allowed_specific_override(
    app: App, client: AsyncClient
):
    plugin = RouteTestExtension("/test_complex", ComplexTestRoute)
    app.add_extension(plugin)

    # ComplexTestRoute has GET and POST (form) handlers. Try PUT.
    response = await client.put("/test_complex")
    assert response.status_code == 405
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_method_not_allowed_no_override(app: App, client: AsyncClient):
    class SimpleGetRoute(Route):
        @handle.GET
        async def get_handler(self) -> Annotated[str, TextResponse]:
            return "GET only"

        # No custom MNA handler

    plugin = RouteTestExtension("/test_simple_get", SimpleGetRoute)
    app.add_extension(plugin)

    response = await client.post("/test_simple_get")
    assert response.status_code == 405
    # Check for default MNA message from app or generic from Route's __call__
    # Based on Route.__call__, it should list allowed methods from __method_handlers__ / __form_handlers__
    # The HTTPMethodNotAllowedException it raises contains this list.
    # The app's default 405 handler will use this.
    assert "Method Not Allowed" in response.text  # Generic check
    assert "GET" in response.headers.get(
        "Allow", ""
    )  # Default handler should set Allow header
    assert plugin.plugin_registered_route


# --- Tests for Annotated Responses ---


@pytest.mark.asyncio
async def test_annotated_json_response(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_json_annotated", JsonAnnotatedRoute)
    app.add_extension(plugin)

    response = await client.get("/test_json_annotated")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == [
        {"id": 1, "name": "Test User"},
        {"id": 2, "name": "Another User"},
    ]
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_annotated_text_response(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_text_annotated", TextAnnotatedRoute)
    app.add_extension(plugin)

    response = await client.get("/test_text_annotated")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]  # Allow for charset
    assert response.text == "Hello from annotated text!"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_raw_dict_handler_without_response_type_errors(
    app: App, client: AsyncClient
):
    """
    Tests that a handler returning a raw dict without an Annotated response type
    or returning a Response instance causes a 500 error.
    """
    plugin = RouteTestExtension("/test_raw_dict_error", RawDictRoute)
    app.add_extension(plugin)

    response = await client.get("/test_raw_dict_error")
    assert response.status_code == 500
    # Check for the app's error message about unsupported return type
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_raw_string_handler_without_response_type_errors(
    app: App, client: AsyncClient
):
    """
    Tests that a handler returning a raw string without an Annotated response type
    or returning a Response instance causes a 500 error.
    """
    plugin = RouteTestExtension("/test_raw_string_error", RawStringRoute)
    app.add_extension(plugin)

    response = await client.get("/test_raw_string_error")
    assert response.status_code == 500
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_direct_response_instance(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_direct_response", DirectResponseInstanceRoute)
    app.add_extension(plugin)

    response = await client.get("/test_direct_response")
    assert response.status_code == 201
    assert response.text == "Direct Response instance."
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_jinja_tuple_return(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_jinja_tuple", JinjaTupleReturnRoute)
    app.add_extension(plugin)

    # Test that jinja tuple handling works (actual template rendering tested elsewhere)
    await client.get("/test_jinja_tuple")
    assert plugin.plugin_registered_route


# --- Tests for Parameter Injection ---


@pytest.mark.asyncio
async def test_parameter_injection_query(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    response = await client.get("/test_param_injection?id=123")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "123"
    assert data["source"] == "query"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_header(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    response = await client.get(
        "/test_param_injection", headers={"Authorization": "Bearer token123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auth_token"] == "Bearer token123"
    assert data["source"] == "header"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_cookie(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    response = await client.get(
        "/test_param_injection", cookies={"session_id": "sess123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess123"
    assert data["source"] == "cookie"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_with_defaults(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    response = await client.get("/test_param_injection")
    assert response.status_code == 200
    data = response.json()
    assert data["optional_param"] == "default_value"
    assert data["source"] == "query_with_default"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_multiple_params(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    response = await client.get(
        "/test_param_injection?id=456",
        headers={"Authorization": "Bearer multi"},
        cookies={"session_id": "multi_sess"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "456"
    assert data["auth_token"] == "Bearer multi"
    assert data["session_id"] == "multi_sess"
    assert data["source"] == "multiple"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_fallback(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_injection", ParameterInjectionRoute)
    app.add_extension(plugin)

    # No parameters provided, should fall back to the generic handler
    response = await client.get("/test_param_injection")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] in ["query_with_default", "fallback"]  # Could match either
    assert plugin.plugin_registered_route


# --- Tests for Multiple GET Handlers and Signature Matching ---


@pytest.mark.asyncio
async def test_multiple_get_handlers_user_id(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_multiple_get", MultipleGetHandlersRoute)
    app.add_extension(plugin)

    response = await client.get("/test_multiple_get?user_id=123")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "user_id"
    assert data["user_id"] == "123"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_multiple_get_handlers_category(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_multiple_get", MultipleGetHandlersRoute)
    app.add_extension(plugin)

    response = await client.get("/test_multiple_get?category=electronics")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "category"
    assert data["category"] == "electronics"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_multiple_get_handlers_both_params(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_multiple_get", MultipleGetHandlersRoute)
    app.add_extension(plugin)

    response = await client.get("/test_multiple_get?user_id=123&category=electronics")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "both"
    assert data["user_id"] == "123"
    assert data["category"] == "electronics"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_multiple_get_handlers_fallback(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_multiple_get", MultipleGetHandlersRoute)
    app.add_extension(plugin)

    response = await client.get("/test_multiple_get")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "fallback"
    assert data["message"] == "no specific parameters"
    assert plugin.plugin_registered_route


# --- Tests for Parameter Injection Failures ---


@pytest.mark.asyncio
async def test_parameter_injection_required_missing(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_param_failure", ParameterInjectionFailureRoute)
    app.add_extension(plugin)

    # Missing required parameter should result in error
    response = await client.get("/test_param_failure")
    assert response.status_code in [
        400,
        500,
    ]  # Could be either depending on error handling
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_parameter_injection_with_default_fallback(app: App, client: AsyncClient):
    plugin = RouteTestExtension(
        "/test_param_default", ParameterInjectionWithDefaultRoute
    )
    app.add_extension(plugin)

    # Should use the handler with default value
    response = await client.get("/test_param_default")
    assert response.status_code == 200
    data = response.json()
    assert data["optional_param"] == "default"
    assert plugin.plugin_registered_route


# --- Tests for Handler Scoring System ---


@pytest.mark.asyncio
async def test_handler_scoring_high_score(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_scoring", HandlerScoringRoute)
    app.add_extension(plugin)

    # Provide both parameters - should match high score handler
    response = await client.get("/test_scoring?param1=value1&param2=value2")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "high_score"
    assert data["param1"] == "value1"
    assert data["param2"] == "value2"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_handler_scoring_medium_score(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_scoring", HandlerScoringRoute)
    app.add_extension(plugin)

    # Provide only one parameter - should match medium score handler
    response = await client.get("/test_scoring?param1=value1")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "medium_score"
    assert data["param1"] == "value1"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_handler_scoring_low_score(app: App, client: AsyncClient):
    plugin = RouteTestExtension("/test_scoring", HandlerScoringRoute)
    app.add_extension(plugin)

    # Provide no parameters - should match low score handler
    response = await client.get("/test_scoring")
    assert response.status_code == 200
    data = response.json()
    assert data["handler"] == "low_score"
    assert plugin.plugin_registered_route
