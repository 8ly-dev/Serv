import pytest
from httpx import AsyncClient

from serv.app import App
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.exceptions import ServException, HTTPNotFoundException
from tests.helpers import RouteAddingPlugin, EventWatcherPlugin
from bevy import dependency

# Custom exceptions for testing
class MyCustomError(ServException):
    status_code = 418 # I'm a teapot
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class AnotherCustomError(ServException):
    status_code = 419 # Another custom status
    pass

class YetAnotherError(Exception): # Not inheriting from ServException
    pass

@pytest.mark.asyncio
async def test_custom_error_handler_invoked(app: App, client: AsyncClient):
    custom_handler_called_with = None

    async def my_error_handler(error: MyCustomError, response: ResponseBuilder = dependency()):
        nonlocal custom_handler_called_with
        custom_handler_called_with = error
        response.set_status(error.status_code)
        response.content_type("application/json")
        response.body(f'{{"error": "Custom handled: {error.message}"}}')

    app.add_error_handler(MyCustomError, my_error_handler)

    async def route_that_raises(request: Request):
        raise MyCustomError("Something custom went wrong")

    plugin = RouteAddingPlugin("/custom_error", route_that_raises, methods=["GET"])
    app.add_plugin(plugin)

    response = await client.get("/custom_error")
    assert response.status_code == 418
    assert response.json() == {"error": "Custom handled: Something custom went wrong"}
    assert isinstance(custom_handler_called_with, MyCustomError)
    assert custom_handler_called_with.message == "Something custom went wrong"

@pytest.mark.asyncio
async def test_default_handler_for_serv_exception_subclass(app: App, client: AsyncClient):
    # This error type does not have a specific handler registered
    async def route_that_raises_another(request: Request):
        raise AnotherCustomError("This is another custom error")

    plugin = RouteAddingPlugin("/another_custom_error", route_that_raises_another, methods=["GET"])
    app.add_plugin(plugin)

    response = await client.get("/another_custom_error")
    assert response.status_code == 419 # Status from the exception itself
    # Default error handler produces HTML
    assert "<h1>Error 419</h1>" in response.text
    assert "<p>AnotherCustomError: This is another custom error</p>" in response.text 

@pytest.mark.asyncio
async def test_default_handler_for_generic_exception(app: App, client: AsyncClient):
    async def route_that_raises_generic(request: Request):
        raise YetAnotherError("A generic problem")

    plugin = RouteAddingPlugin("/generic_error", route_that_raises_generic, methods=["GET"])
    app.add_plugin(plugin)

    response = await client.get("/generic_error")
    assert response.status_code == 500 # Default for non-ServException
    assert "<h1>Error 500</h1>" in response.text
    assert "<p>YetAnotherError: A generic problem</p>" in response.text
    assert "<p>Traceback:</p>" in response.text # Should include traceback for 500

@pytest.mark.asyncio
async def test_error_in_error_handler_falls_to_default(app: App, client: AsyncClient):
    error_handler_one_called = False
    original_error_message = "Initial problem"

    async def faulty_error_handler(error: MyCustomError, response: ResponseBuilder = dependency()):
        nonlocal error_handler_one_called
        error_handler_one_called = True
        raise ValueError("Error inside the error handler!")

    app.add_error_handler(MyCustomError, faulty_error_handler)

    async def route_that_raises(request: Request):
        raise MyCustomError(original_error_message)

    plugin = RouteAddingPlugin("/faulty_handler_error", route_that_raises, methods=["GET"])
    app.add_plugin(plugin)

    response = await client.get("/faulty_handler_error")
    assert error_handler_one_called
    assert response.status_code == 500 # Should fall back to the ultimate default 500 handler
    assert "<h1>Error 500</h1>" in response.text
    # Check that the new error (from the faulty handler) is shown
    assert "<p>ValueError: Error inside the error handler!</p>" in response.text
    # And it should also show the traceback for this new 500 error
    assert "<p>Traceback:</p>" in response.text
    # Optionally, one could check for chained exceptions if your logger/formatter shows __context__

@pytest.mark.asyncio
async def test_request_end_event_on_handled_error(app: App, client: AsyncClient):
    event_watcher = EventWatcherPlugin()
    app.add_plugin(event_watcher)

    custom_error_message = "Test handled error event"
    async def route_that_raises_my_error(request: Request):
        raise MyCustomError(custom_error_message)
    
    # No custom handler for MyCustomError, so _default_error_handler will be used via fallback
    # for ServException subclasses, but it will use MyCustomError.status_code (418)

    plugin = RouteAddingPlugin("/error_event", route_that_raises_my_error, methods=["GET"])
    app.add_plugin(plugin)

    await client.get("/error_event")

    end_event_data = None
    for name, kwargs_evt in event_watcher.events_seen:
        if name == "app.request.end":
            end_event_data = kwargs_evt
            break
    
    assert end_event_data is not None, "app.request.end event was not seen"
    assert "error" in end_event_data
    assert isinstance(end_event_data["error"], MyCustomError)
    assert str(end_event_data["error"]) == custom_error_message 