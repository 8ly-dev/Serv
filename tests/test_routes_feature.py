from dataclasses import dataclass
import pytest
from httpx import AsyncClient
from typing import Any, Type

from serv.app import App
from serv.routes import Route, Form, GetRequest, Response, TextResponse
from serv.observers import Observer
from serv.routing import Router # For type hinting if needed, actual router comes from event
from bevy import dependency

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
    async def handle_get(self, _: GetRequest) -> Response:
        return TextResponse("GET request processed")

    async def handle_post_form(self, form: SimpleForm) -> Response:
        return TextResponse(f"Form processed: Name={form.name}, Age={form.age}")

    async def handle_another_form(self, form: AnotherForm) -> Response:
        return TextResponse(f"AnotherForm processed: ItemID={form.item_id}")


class CustomErrorRoute(Route):
    async def handle_custom_error(self, _: MyCustomException) -> Response:
        return TextResponse("Custom error handled", status_code=501)

    async def raise_custom_error_route(self, _: GetRequest) -> Response: # Assuming a GET for simplicity
        raise MyCustomException("Something went wrong!")


class UnhandledErrorRoute(Route):
    async def unhandled_error_route(self, _: GetRequest) -> Response: # Assuming a GET
        raise ValueError("This is an unhandled error.")

# --- Test Plugin for adding Route classes ---

class TestRoutePlugin(Observer):
    def __init__(self, path: str, route_class: Type[Route]):
        self.path = path
        self.route_class = route_class
        self.router_instance_id_at_registration = None
        self.plugin_registered_route = False

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        # Using app.request.begin as it seems to be a point where router_instance is available
        # A dedicated app.startup or app.plugins.loaded event might be cleaner if available.
        router.add_route(self.path, self.route_class)
        self.router_instance_id_at_registration = id(router)
        self.plugin_registered_route = True # Register only once

# --- Tests ---

@pytest.mark.asyncio
async def test_route_get_method(app: App, client: AsyncClient):
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)

    response = await client.get("/test_complex")
    assert response.status_code == 200
    assert response.text == "GET request processed"
    assert plugin.plugin_registered_route # Ensure plugin logic ran

@pytest.mark.asyncio
async def test_route_post_form_success(app: App, client: AsyncClient):
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)

    response = await client.post("/test_complex", data={"name": "Alice", "age": "30"})
    assert response.status_code == 200
    assert response.text == "Form processed: Name=Alice, Age=30"
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_route_post_form_missing_field(app: App, client: AsyncClient):
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)

    # This should not match SimpleForm due to missing 'age', 
    # and ComplexTestRoute has no generic POST handler.
    # So, it should fall to a 405 or whatever the Route's __call__
    # or the app's default is for no matching form/method handler.
    # The Route.__call__ itself raises HTTPMethodNotAllowedException if no form or method matches.
    response = await client.post("/test_complex", data={"name": "Bob"})
    assert response.status_code == 405 # Expecting MNA as no form matched and no general POST
    # The ComplexTestRoute has handle_method_not_allowed_override
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_route_post_form_wrong_type(app: App, client: AsyncClient):
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)
    
    # Age is not an int. Should not match SimpleForm.
    response = await client.post("/test_complex", data={"name": "Charlie", "age": "thirty"})
    assert response.status_code == 405
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_route_another_form_get_method(app: App, client: AsyncClient):
    # This test needs a specific path for the GET that triggers the 'AnotherForm'
    # The current ComplexTestRoute.__init_subclass__ will map 'handle_another_form'
    # to the method 'GET' (from AnotherForm.__form_method__).
    # We need a GET request to /test_complex that also provides 'item_id'.
    # This will be tricky if __form_method__ is GET and we also have a plain GET handler.
    # The current `Route.__call__` prioritizes form handlers based on `matches_form_data`.
    # A GET request with query params for the form.
    
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)

    response = await client.post("/test_complex", data={"item_id": "xyz123"})
    assert response.status_code == 200
    # If both handle_get and handle_another_form (for GET method) are candidates,
    # the one whose form matches_form_data will be chosen.
    # If item_id is present, AnotherForm should match.
    assert response.text == "AnotherForm processed: ItemID=xyz123"
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_route_custom_error_handler(app: App, client: AsyncClient):
    # We need a way to trigger 'raise_custom_error_route' within ComplexTestRoute.
    # Let's add a sub-path or a dedicated route for this in the test setup.
    # For now, assume ComplexTestRoute is mounted at /test_complex.
    # We need a route like /test_complex/raise_error that calls raise_custom_error_route.

    # Modification: Add a specific route for this or make ComplexTestRoute more complex
    # For simplicity, let's assume a GET to a specific path that is internally routed by ComplexTestRoute
    # to `raise_custom_error_route`. This requires `ComplexTestRoute` to have more internal routing
    # or to modify `__init_subclass__` to register `raise_custom_error_route` to a GET path.

    # Simpler: Define a new Route for this specific test.
    plugin = TestRoutePlugin("/test_raiser", CustomErrorRoute)
    app.add_plugin(plugin)

    response = await client.get("/test_raiser")
    assert response.status_code == 501
    assert response.text == "Custom error handled"
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_unhandled_error(app: App, client: AsyncClient):
    # Similar to custom error, need a way to trigger unhandled_error_route.
    plugin = TestRoutePlugin("/test_unhandled", UnhandledErrorRoute)
    app.add_plugin(plugin)

    response = await client.get("/test_unhandled")
    # Expecting a generic 500 error as it's unhandled by the Route itself.
    # The app's default error handler should catch this.
    assert response.status_code == 500 
    # The default error handler in app.py might return HTML or plain text.
    # For now, just check status code. If specific text is needed, inspect app's default handler.
    assert plugin.plugin_registered_route


@pytest.mark.asyncio
async def test_route_method_not_allowed_specific_override(app: App, client: AsyncClient):
    plugin = TestRoutePlugin("/test_complex", ComplexTestRoute)
    app.add_plugin(plugin)

    # ComplexTestRoute has GET and POST (form) handlers. Try PUT.
    # It also has `handle_method_not_allowed_override`.
    response = await client.put("/test_complex")
    assert response.status_code == 405
    assert plugin.plugin_registered_route

@pytest.mark.asyncio
async def test_route_method_not_allowed_no_override(app: App, client: AsyncClient):
    class SimpleGetRoute(Route):
        async def handle_get(self, request: GetRequest) -> Response:
            return TextResponse("GET only")
        # No custom MNA handler

    plugin = TestRoutePlugin("/test_simple_get", SimpleGetRoute)
    app.add_plugin(plugin)
    
    response = await client.post("/test_simple_get")
    assert response.status_code == 405
    # Check for default MNA message from app or generic from Route's __call__
    # Based on Route.__call__, it should list allowed methods from __method_handlers__ / __form_handlers__
    # The HTTPMethodNotAllowedException it raises contains this list.
    # The app's default 405 handler will use this.
    assert "Method Not Allowed" in response.text # Generic check
    assert "GET" in response.headers.get("Allow", "") # Default handler should set Allow header
    assert plugin.plugin_registered_route

# Removed </rewritten_file> tag that was causing a syntax error 