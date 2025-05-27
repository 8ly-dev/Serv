"""
Helper utilities for tests.
"""

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from bevy import dependency
from bevy.containers import Container

from serv.plugins import Listener
from serv.plugins.importer import Importer
from serv.plugins.loader import PluginSpec
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routing import Router


def patch_plugin_spec_on_module(plugin: Listener):
    """Patch the plugin's module with its __plugin_spec__ for testing.

    This is needed because test plugins are standalone and don't go through
    the normal plugin loading system that sets module.__plugin_spec__.
    """
    if hasattr(plugin, "_plugin_spec"):
        module = sys.modules[plugin.__module__]
        module.__plugin_spec__ = plugin._plugin_spec


class RouteAddingPlugin(Listener):
    def __init__(
        self,
        path: str,
        handler: Callable[..., Awaitable[None]],
        methods: list[str] | None = None,
    ):
        self.path = path
        self.handler = handler
        self.methods = methods
        self.was_called = 0
        self.received_kwargs = None
        # Define _plugin_spec and patch module BEFORE super().__init__
        self._plugin_spec = PluginSpec(
            config={
                "name": "RouteAddingPlugin",
                "description": "A test plugin that adds routes",
                "version": "0.1.0",
                "author": "Test Author",
            },
            path=Path(__file__).parent,
            override_settings={},
            importer=create_mock_importer(Path(__file__).parent),
        )
        patch_plugin_spec_on_module(self)
        super().__init__()
        # self._stand_alone = True # No longer needed here for Plugin base class init

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler_wrapper, methods=self.methods)

    async def _handler_wrapper(
        self,
        request: Request = dependency(),
        container: Container = dependency(),
        **path_params,
    ):
        self.was_called += 1
        self.received_kwargs = {
            **path_params,
            "request": request,
            "container": container,
        }  # For inspection

        # Call the original handler (e.g., hello_handler from the test)
        # using the per-request container. Path parameters are passed explicitly.
        # Other dependencies (like Request, ResponseBuilder) should be declared
        # in self.handler's signature with ` = dependency()` if needed.
        await container.call(self.handler, **path_params)


def create_mock_importer(directory: Path = None) -> Importer:
    """Create a mock importer for testing purposes."""
    if directory is None:
        directory = Path(".")

    mock_importer = MagicMock(spec=Importer)
    mock_importer.directory = directory
    mock_importer.load_module = MagicMock()
    mock_importer.using_sub_module = MagicMock(return_value=mock_importer)
    return mock_importer


def create_test_plugin_spec(
    name: str = "TestPlugin",
    version: str = "0.1.0",
    path: Path = None,
    override_settings: dict[str, Any] = None,
    importer: Importer = None,
) -> PluginSpec:
    """Create a PluginSpec for testing purposes."""
    if path is None:
        path = Path(".")
    if override_settings is None:
        override_settings = {}
    if importer is None:
        importer = create_mock_importer(path)

    config = {
        "name": name,
        "version": version,
        "description": "A test plugin",
        "author": "Test Author",
    }

    return PluginSpec(
        config=config, path=path, override_settings=override_settings, importer=importer
    )


class EventWatcherPlugin(Listener):
    def __init__(self):
        self.events_seen = []
        # Define _plugin_spec and patch module BEFORE super().__init__
        self._plugin_spec = create_test_plugin_spec(
            name="EventWatcherPlugin", path=Path(__file__).parent
        )
        patch_plugin_spec_on_module(self)
        super().__init__()
        # self._stand_alone = True # No longer needed here for Plugin base class init

    async def on(self, event_name: str, **kwargs: Any) -> None:
        self.events_seen.append((event_name, kwargs))


# Example of a simple middleware for testing
# Middleware are defined as async generator factories
async def example_header_middleware(
    request: Request = dependency(), response: ResponseBuilder = dependency()
) -> None:
    # Code here runs before the next middleware/handler
    response.add_header("X-Test-Middleware-Before", "active")
    yield
    # Code here runs after the next middleware/handler
    response.add_header("X-Test-Middleware-After", "active")
