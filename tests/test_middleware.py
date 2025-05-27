from collections.abc import AsyncIterator

import pytest
from bevy import dependency
from httpx import AsyncClient

from serv.app import App
from serv.exceptions import (
    HTTPNotFoundException,  # For testing middleware error handling
)
from serv.requests import Request
from serv.responses import ResponseBuilder
from tests.helpers import RouteAddingExtension, example_header_middleware


@pytest.mark.asyncio
async def test_single_middleware_modifies_headers(app: App, client: AsyncClient):
    app.add_middleware(example_header_middleware)  # Adds X-Test-Middleware-Before/After

    async def ok_handler(response: ResponseBuilder = dependency()):
        response.body("OK")

    plugin = RouteAddingExtension("/mw_headers", ok_handler, methods=["GET"])
    app.add_extension(plugin)

    response = await client.get("/mw_headers")
    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers.get("X-Test-Middleware-Before") == "active"
    assert response.headers.get("X-Test-Middleware-After") == "active"


@pytest.mark.asyncio
async def test_multiple_middleware_order(app: App, client: AsyncClient):
    order_tracker = []

    async def middleware_one() -> AsyncIterator[None]:
        order_tracker.append("mw1_before")
        yield
        order_tracker.append("mw1_after")

    async def middleware_two(
        response: ResponseBuilder = dependency(),
    ) -> AsyncIterator[None]:
        order_tracker.append("mw2_before")
        response.add_header("X-MW2", "active")
        yield
        order_tracker.append("mw2_after")

    app.add_middleware(middleware_one)
    app.add_middleware(middleware_two)

    async def simple_handler(response: ResponseBuilder = dependency()):
        order_tracker.append("handler_called")
        response.body("Handler response")

    plugin = RouteAddingExtension("/mw_order", simple_handler, methods=["GET"])
    app.add_extension(plugin)

    response = await client.get("/mw_order")
    assert response.status_code == 200
    assert response.text == "Handler response"
    assert response.headers.get("X-MW2") == "active"
    assert order_tracker == [
        "mw1_before",
        "mw2_before",
        "handler_called",
        "mw2_after",
        "mw1_after",
    ]


@pytest.mark.asyncio
async def test_middleware_exception_before_yield(app: App, client: AsyncClient):
    cleanup_called = False

    async def error_mw_before() -> AsyncIterator[None]:
        # This middleware will raise an error before yielding
        raise ValueError("Error in MW before yield")
        yield  # Unreachable
        # Nonlocal cleanup_called not ideal in async gen, use attribute or other state for real mw

    async def outer_mw() -> AsyncIterator[None]:
        nonlocal cleanup_called
        try:
            yield
        finally:
            cleanup_called = (
                True  # This should be called if error_mw_before.athrow works
            )

    app.add_middleware(outer_mw)
    app.add_middleware(error_mw_before)

    async def test_route_handler(response: ResponseBuilder = dependency()):
        response.body("Should not be reached")

    plugin = RouteAddingExtension(
        "/mw_error_before", test_route_handler, methods=["GET"]
    )
    app.add_extension(plugin)

    response = await client.get("/mw_error_before")
    assert response.status_code == 500  # Default error handler
    assert "Error in MW before yield" in response.text
    # Test if outer_mw's cleanup (after yield part) was called via athrow
    # This depends on how athrow is handled and if the generator can resume to run finally/after yield.
    # For simple yield, athrow injects exception at yield point.
    # If exception before yield, the generator might not even be entered for athrow in some Python versions/setups.
    # The app's current _run_middleware_stack tries to athrow on the iterator instance.
    # If the iterator isn't advanced to its first yield, athrow might not have the intended effect
    # on its *own* cleanup. However, the outer_mw *should* still have its cleanup run.
    # Let's adjust the test to reflect what the current app.py does: athrow on *successfully started* middleware.
    # In this specific case, error_mw_before won't be in the `stack` to get an athrow because it errors during setup.
    # So, `cleanup_called` for `outer_mw` will depend on whether the exception from `error_mw_before`
    # during its setup phase correctly triggers `athrow` on `outer_mw`.

    # Given current app.py: error_mw_before errors in the first loop, so it's not added to stack.
    # The error then propagates, and the reversed(stack) for cleanup will only contain successfully started middleware.
    # Thus, outer_mw, if it started, will get an athrow.
    assert (
        cleanup_called
    )  # This will be true if outer_mw was started and then got an athrow


@pytest.mark.asyncio
async def test_middleware_exception_after_yield(app: App, client: AsyncClient):
    # This test will be more straightforward for `athrow`
    async def error_mw_after() -> AsyncIterator[None]:
        yield
        raise ValueError("Error in MW after yield")

    app.add_middleware(error_mw_after)

    async def test_route_handler(response: ResponseBuilder = dependency()):
        response.body("Handler was called")

    plugin = RouteAddingExtension(
        "/mw_error_after", test_route_handler, methods=["GET"]
    )
    app.add_extension(plugin)

    response = await client.get("/mw_error_after")
    assert response.status_code == 500
    assert "Error in MW after yield" in response.text


@pytest.mark.asyncio
async def test_handler_exception_propagates_to_middleware(
    app: App, client: AsyncClient
):
    cleanup_mw_called = False

    async def observing_mw() -> AsyncIterator[None]:
        nonlocal cleanup_mw_called
        error_in_athrow = None
        try:
            yield
        except HTTPNotFoundException as e:  # Specific exception from handler
            error_in_athrow = e
            # Middleware could potentially handle it and change response, or re-raise
            # For this test, we just note it and let it propagate by default
            raise
        finally:
            # This should always be called, even if athrow happened
            cleanup_mw_called = True
            assert isinstance(
                error_in_athrow, HTTPNotFoundException
            )  # Check that the correct error was passed

    app.add_middleware(observing_mw)

    async def error_handler(request: Request = dependency()):
        raise HTTPNotFoundException(f"Simulated error for {request.path}")

    plugin = RouteAddingExtension("/handler_error", error_handler, methods=["GET"])
    app.add_extension(plugin)

    response = await client.get("/handler_error")
    assert response.status_code == 404  # Our specific 404 handler should take over
    assert (
        "404 Not Found: The requested resource (/handler_error) was not found."
        == response.text
    )
    assert cleanup_mw_called


# A test for athrow itself raising an error is more complex to set up with the current helper structure.
# It would involve a middleware whose __anext__ or __athrow__ method itself raises an unexpected error.
# The app.py code for _run_middleware_stack has logging for "Error during unwinding of middleware",
# which is the main observable effect if an athrow fails badly.
