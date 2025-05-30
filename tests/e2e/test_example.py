"""
Example end-to-end tests demonstrating the use of the e2e testing tools.

This file contains examples of how to use the end-to-end testing tools:
1. Testing with a basic app and client
2. Using the TestAppBuilder for more complex setups
3. Creating custom app configurations for specific test cases
"""

from pathlib import Path

import pytest
from bevy import dependency

from serv.extensions import Extension, on
from serv.responses import ResponseBuilder
from serv.routing import Router
from tests.e2e.helpers import AppBuilder, create_test_client
from tests.helpers import create_test_extension_spec


class SimpleTextExtension(Extension):
    """Simple plugin that adds a route returning plain text."""

    def __init__(self, path: str, text: str):
        # Set up the plugin spec on the module before calling super().__init__()
        self._extension_spec = create_test_extension_spec(
            name="SimpleTextExtension", version="0.1.0", path=Path(__file__).parent
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self.path = path
        self.text = text
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler, methods=["GET"])

    async def _handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body(self.text)


class JsonExtension(Extension):
    """Simple plugin that adds a route returning JSON data."""

    def __init__(self, path: str, data: dict):
        # Set up the plugin spec on the module before calling super().__init__()
        self._extension_spec = create_test_extension_spec(
            name="JsonExtension", version="0.1.0", path=Path(__file__).parent
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self.path = path
        self.data = data
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler, methods=["GET"])

    async def _handler(self, response: ResponseBuilder = dependency()):
        import json

        response.content_type("application/json")
        response.body(json.dumps(self.data))


@pytest.mark.asyncio
async def test_basic_usage():
    """Basic usage of create_test_client with a simple plugin."""
    # Create a plugin that adds a route
    hello_plugin = SimpleTextExtension("/hello", "Hello, World!")

    # Use create_test_client directly
    async with create_test_client(plugins=[hello_plugin]) as client:
        # Make a request to the app
        response = await client.get("/hello")

        # Check the response
        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_with_app_factory(app_factory):
    """Using create_test_client with a custom app factory."""

    def create_custom_app():
        # Create an app with custom configuration
        app = app_factory()

        # Add plugins
        app.add_extension(SimpleTextExtension("/greet", "Greetings!"))
        app.add_extension(JsonExtension("/data", {"message": "This is JSON data"}))

        return app

    # Use create_test_client with the app factory
    async with create_test_client(app_factory=create_custom_app) as client:
        # Test plain text endpoint
        text_response = await client.get("/greet")
        assert text_response.status_code == 200
        assert text_response.text == "Greetings!"

        # Test JSON endpoint
        json_response = await client.get("/data")
        assert json_response.status_code == 200
        assert json_response.json() == {"message": "This is JSON data"}


@pytest.mark.asyncio
async def test_with_app_builder(app_builder: AppBuilder):
    """Using the TestAppBuilder for a more complex setup."""
    # Configure the app builder
    builder = (
        app_builder.with_plugin(SimpleTextExtension("/hello", "Hello from builder!"))
        .with_plugin(JsonExtension("/api/data", {"count": 42, "items": ["foo", "bar"]}))
        .with_dev_mode(True)
    )

    # Use the builder to create a test client
    async with builder.build_client() as client:
        # Test text endpoint
        text_response = await client.get("/hello")
        assert text_response.status_code == 200
        assert text_response.text == "Hello from builder!"

        # Test JSON endpoint
        json_response = await client.get("/api/data")
        assert json_response.status_code == 200
        assert json_response.json() == {"count": 42, "items": ["foo", "bar"]}


@pytest.mark.asyncio
async def test_with_test_client_fixture(test_client, app):
    """Using the test_client fixture."""
    # Add routes to the app
    plugin = SimpleTextExtension("/fixture-test", "Testing with fixture!")
    app.add_extension(plugin)

    # Test the endpoint
    response = await test_client.get("/fixture-test")
    assert response.status_code == 200
    assert response.text == "Testing with fixture!"


@pytest.mark.asyncio
async def test_multiple_clients():
    """Testing with multiple client instances for different app configurations."""
    # First app with one configuration
    async with create_test_client(
        plugins=[SimpleTextExtension("/app1", "App 1 Response")]
    ) as client1:
        response1 = await client1.get("/app1")
        assert response1.status_code == 200
        assert response1.text == "App 1 Response"

    # Second app with different configuration
    async with create_test_client(
        plugins=[SimpleTextExtension("/app2", "App 2 Response")]
    ) as client2:
        response2 = await client2.get("/app2")
        assert response2.status_code == 200
        assert response2.text == "App 2 Response"

        # This endpoint doesn't exist in the second app
        response_not_found = await client2.get("/app1")
        assert response_not_found.status_code == 404
