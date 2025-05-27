import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.exceptions import ServException
from serv.requests import Request
from serv.responses import ResponseBuilder
from tests.helpers import EventWatcherExtension, RouteAddingExtension


# Custom exceptions for testing
class MyCustomError(ServException):
    status_code = 418  # I'm a teapot
    message = "This is a custom error."


class AnotherCustomError(ServException):
    status_code = 419  # Authentication Timeout (unofficial)
    message = "Another type of custom error."


class YetAnotherError(Exception):
    # Not a ServException, so should be handled by the generic 500 handler
    pass


@pytest.mark.asyncio
async def test_custom_error_handler_invoked(app: App, client: AsyncClient):
    custom_handler_called_with = None

    async def my_error_handler(
        error: MyCustomError, response: ResponseBuilder = dependency()
    ):
        nonlocal custom_handler_called_with
        custom_handler_called_with = error
        response.set_status(error.status_code)
        response.content_type("application/json")
        response.body(f'{{"error": "Custom handled: {error.message}"}}')

    app.add_error_handler(MyCustomError, my_error_handler)

    async def route_that_raises(request: Request = dependency()):
        raise MyCustomError("Something custom went wrong")

    plugin = RouteAddingExtension("/custom_error", route_that_raises, methods=["GET"])
    app.add_extension(plugin)

    response = await client.get("/custom_error")
    assert response.status_code == 418
    assert custom_handler_called_with is not None
    assert isinstance(custom_handler_called_with, MyCustomError)
    assert custom_handler_called_with.message == "Something custom went wrong"
    assert response.json() == {"error": "Custom handled: Something custom went wrong"}


@pytest.mark.asyncio
async def test_default_handler_for_serv_exception_subclass(
    app: App, client: AsyncClient
):
    # This error type does not have a specific handler registered
    async def route_that_raises_another(request: Request = dependency()):
        raise AnotherCustomError("This is another custom error")

    plugin = RouteAddingExtension(
        "/another_custom_error", route_that_raises_another, methods=["GET"]
    )
    app.add_extension(plugin)

    response = await client.get("/another_custom_error")
    assert response.status_code == 419  # Status from the exception itself
    # Default handler for ServException should use its status code and message (or type name)
    # The current _default_error_handler produces HTML, so check for key parts
    assert "419 Error" in response.text
    assert "This is another custom error" in response.text


@pytest.mark.asyncio
async def test_default_handler_for_generic_exception(app: App, client: AsyncClient):
    async def route_that_raises_generic(request: Request = dependency()):
        raise YetAnotherError("A generic problem")

    plugin = RouteAddingExtension(
        "/generic_error", route_that_raises_generic, methods=["GET"]
    )
    app.add_extension(plugin)

    response = await client.get("/generic_error")
    assert response.status_code == 500  # Default for non-ServException
    assert "500 Error" in response.text
    assert "A generic problem" in response.text


@pytest.mark.asyncio
async def test_error_in_error_handler_falls_to_default(app: App, client: AsyncClient):
    error_handler_one_called = False
    original_error_message = "Initial problem"

    async def faulty_error_handler(
        error: MyCustomError, response: ResponseBuilder = dependency()
    ):
        nonlocal error_handler_one_called
        error_handler_one_called = True
        raise ValueError("Error inside the error handler!")  # This error will be caught

    app.add_error_handler(MyCustomError, faulty_error_handler)

    async def route_that_raises(request: Request = dependency()):
        raise MyCustomError(original_error_message)

    plugin = RouteAddingExtension(
        "/faulty_handler_error", route_that_raises, methods=["GET"]
    )
    app.add_extension(plugin)

    response = await client.get("/faulty_handler_error")
    assert error_handler_one_called
    assert response.status_code == 500  # Should fall to the ultimate default handler
    # Check that the response indicates the error from faulty_error_handler AND the original error context
    text = response.text
    assert "500 Error" in text
    assert "Error inside the error handler!" in text


@pytest.mark.asyncio
async def test_request_end_event_on_handled_error(app: App, client: AsyncClient):
    event_watcher = EventWatcherExtension()
    app.add_extension(event_watcher)

    custom_error_message = "Test handled error event"

    async def route_that_raises_my_error(request: Request = dependency()):
        raise MyCustomError(custom_error_message)

    # No custom handler for MyCustomError, so _default_error_handler will be used via fallback
    # for ServException subclasses, but it will use MyCustomError.status_code (418)

    plugin = RouteAddingExtension(
        "/error_event", route_that_raises_my_error, methods=["GET"]
    )
    app.add_extension(plugin)

    await client.get("/error_event")

    end_event_data = None
    for name, kwargs_evt in event_watcher.events_seen:
        if name == "app.request.end":
            end_event_data = kwargs_evt
            break

    assert end_event_data is not None, "app.request.end event was not seen"
    assert "error" in end_event_data
    assert isinstance(end_event_data["error"], MyCustomError)
    assert end_event_data["error"].message == custom_error_message
