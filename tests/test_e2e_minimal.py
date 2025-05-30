"""
Simplified end-to-end tests to validate the basic setup.
"""

from pathlib import Path

import pytest
from bevy import dependency

from serv.extensions import Extension, on
from serv.extensions.loader import ExtensionSpec
from serv.responses import ResponseBuilder
from serv.routing import Router
from tests.e2e_test_helpers import create_test_client


class SimpleExtension(Extension):
    """Super simple plugin that adds a /hello route."""

    def __init__(self):
        # Set up the plugin spec on the module before calling super().__init__()
        from tests.helpers import create_mock_importer

        self._extension_spec = ExtensionSpec(
            config={
                "name": "SimpleExtension",
                "description": "A super simple plugin that adds a /hello route",
                "version": "0.1.0",
                "author": "Test Author",
            },
            path=Path(__file__).parent,
            override_settings={},
            importer=create_mock_importer(Path(__file__).parent),
        )

        # Patch the module's __extension_spec__ for testing BEFORE super().__init__()
        import sys

        module = sys.modules[self.__module__]
        module.__extension_spec__ = self._extension_spec

        super().__init__(stand_alone=True)
        self._stand_alone = True

    @on("app.request.begin")
    async def setup_routes(self, router: Router = dependency()) -> None:
        router.add_route("/hello", self._hello_handler, methods=["GET"])

    async def _hello_handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello, World!")


@pytest.mark.asyncio
async def test_simple_route():
    """Test a simple route with the create_test_client."""
    # Use create_test_client with a simple plugin
    async with create_test_client(plugins=[SimpleExtension()]) as client:
        # Make a request to the app
        response = await client.get("/hello")

        # Check the response
        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
