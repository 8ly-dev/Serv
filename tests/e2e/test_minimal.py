"""
Simplified end-to-end tests demonstrating the most basic usage pattern.
"""
import pytest
from pathlib import Path
from bevy import dependency

from serv.plugins import Plugin
from serv.responses import ResponseBuilder
from serv.routing import Router
from serv.plugin_loader import PluginSpec

from tests.e2e.helpers import create_test_client


class SimplePlugin(Plugin):
    """Super simple plugin that adds a /hello route."""
    
    def __init__(self):
        super().__init__()
        self._stand_alone = True
        self._plugin_spec = PluginSpec(
            config={
                "name": "SimplePlugin",
                "description": "A super simple plugin that adds a /hello route",
                "version": "0.1.0",
                "author": "Test Author"
            },
            path=Path(__file__).parent,
            override_settings={}
        )
        
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route("/hello", self._hello_handler, methods=["GET"])
        
    async def _hello_handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello, World!")


@pytest.mark.asyncio
async def test_simple_route():
    """Test a simple route with the create_test_client."""
    # Use create_test_client with a simple plugin
    async with create_test_client(plugins=[SimplePlugin()]) as client:
        # Make a request to the app
        response = await client.get("/hello")
        
        # Check the response
        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_basic_fixtures(app, test_client):
    """Test using the basic fixtures provided in conftest.py."""
    # Add a plugin to the app
    app.add_plugin(SimplePlugin())
    
    # Make a request
    response = await test_client.get("/hello")
    
    # Check the response
    assert response.status_code == 200
    assert response.text == "Hello, World!" 