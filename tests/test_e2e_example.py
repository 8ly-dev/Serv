"""
Example end-to-end tests demonstrating the use of the e2e_test_helpers module.

This file contains examples of how to use the end-to-end testing tools:
1. Testing with a basic app and client
2. Using the AppBuilder for more complex setups
3. Creating custom app configurations for specific test cases
"""
import pytest
from pathlib import Path
from bevy import dependency

from serv.app import App
from serv.plugins import Plugin
from serv.responses import ResponseBuilder
from serv.routing import Router
from serv.plugins.loader import PluginSpec

from tests.e2e_test_helpers import create_test_client, AppBuilder


class SimpleTextPlugin(Plugin):
    """Simple plugin that adds a route returning plain text."""
    
    def __init__(self, path: str, text: str):
        # Set up the plugin spec on the module before calling super().__init__()
        from tests.helpers import create_mock_importer
        self._plugin_spec = PluginSpec(
            config={
                "name": "SimpleTextPlugin",
                "description": "A simple plugin that returns plain text",
                "version": "0.1.0",
                "author": "Test Author"
            },
            path=Path(__file__).parent,
            override_settings={},
            importer=create_mock_importer(Path(__file__).parent)
        )
        
        # Patch the module's __plugin_spec__ for testing BEFORE super().__init__()
        import sys
        module = sys.modules[self.__module__]
        module.__plugin_spec__ = self._plugin_spec
        
        super().__init__(stand_alone=True)
        self.path = path
        self.text = text
        self._stand_alone = True
        
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler, methods=["GET"])
        
    async def _handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body(self.text)


class JsonPlugin(Plugin):
    """Simple plugin that adds a route returning JSON data."""
    
    def __init__(self, path: str, data: dict):
        # Set up the plugin spec on the module before calling super().__init__()
        from tests.helpers import create_mock_importer
        self._plugin_spec = PluginSpec(
            config={
                "name": "JsonPlugin",
                "description": "A simple plugin that returns JSON data",
                "version": "0.1.0",
                "author": "Test Author"
            },
            path=Path(__file__).parent,
            override_settings={},
            importer=create_mock_importer(Path(__file__).parent)
        )
        
        # Patch the module's __plugin_spec__ for testing BEFORE super().__init__()
        import sys
        module = sys.modules[self.__module__]
        module.__plugin_spec__ = self._plugin_spec
        
        super().__init__(stand_alone=True)
        self.path = path
        self.data = data
        self._stand_alone = True
        
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler, methods=["GET"])
        
    async def _handler(self, response: ResponseBuilder = dependency()):
        import json
        response.content_type("application/json")
        response.body(json.dumps(self.data))


@pytest.mark.asyncio
async def test_basic_usage():
    """Basic usage of create_test_client with a simple plugin."""
    # Create a plugin that adds a route
    hello_plugin = SimpleTextPlugin("/hello", "Hello, World!")
    
    # Use create_test_client directly
    async with create_test_client(plugins=[hello_plugin]) as client:
        # Make a request to the app
        response = await client.get("/hello")
        
        # Check the response
        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_with_app_factory():
    """Using create_test_client with a custom app factory."""
    
    def create_custom_app():
        # Create an app with custom configuration
        app = App(dev_mode=True)
        
        # Add plugins
        app.add_plugin(SimpleTextPlugin("/greet", "Greetings!"))
        app.add_plugin(JsonPlugin("/data", {"message": "This is JSON data"}))
        
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
    """Using the AppBuilder for a more complex setup."""
    # Configure the app builder
    builder = (
        app_builder
        .with_plugin(SimpleTextPlugin("/hello", "Hello from builder!"))
        .with_plugin(JsonPlugin("/api/data", {"count": 42, "items": ["foo", "bar"]}))
        .with_dev_mode(True)
    )
    
    # Use the builder to create a test client
    async with builder.build_client(use_lifespan=False) as client:
        # Test text endpoint
        text_response = await client.get("/hello")
        assert text_response.status_code == 200
        assert text_response.text == "Hello from builder!"
        
        # Test JSON endpoint
        json_response = await client.get("/api/data")
        assert json_response.status_code == 200
        assert json_response.json() == {"count": 42, "items": ["foo", "bar"]}


@pytest.mark.asyncio
async def test_with_app_test_client_fixture(app_test_client):
    """Using the app_test_client fixture from conftest.py."""
    # Create plugins
    plugins = [
        SimpleTextPlugin("/fixture-test", "Testing with fixture!"),
        JsonPlugin("/fixture-json", {"success": True})
    ]
    
    # Use the fixture
    async with app_test_client(plugins=plugins, use_lifespan=False) as client:
        # Test text endpoint
        text_response = await client.get("/fixture-test")
        assert text_response.status_code == 200
        assert text_response.text == "Testing with fixture!"
        
        # Test JSON endpoint
        json_response = await client.get("/fixture-json")
        assert json_response.status_code == 200
        assert json_response.json() == {"success": True}


 