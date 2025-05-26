"""
Helper utilities for tests.
"""
import asyncio
import sys
from typing import Any, Awaitable, Callable
from pathlib import Path
from bevy import dependency
from bevy.containers import Container

from serv.plugins import Plugin
from serv.routing import Router
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.plugins.loader import PluginSpec


def patch_plugin_spec_on_module(plugin: Plugin):
    """Patch the plugin's module with its __plugin_spec__ for testing.
    
    This is needed because test plugins are standalone and don't go through
    the normal plugin loading system that sets module.__plugin_spec__.
    """
    if hasattr(plugin, '_plugin_spec'):
        module = sys.modules[plugin.__module__]
        module.__plugin_spec__ = plugin._plugin_spec


class RouteAddingPlugin(Plugin):
    def __init__(self, path: str, handler: Callable[..., Awaitable[None]], methods: list[str] | None = None):
        super().__init__()
        self.path = path
        self.handler = handler
        self.methods = methods
        self.was_called = 0
        self.received_kwargs = None
        self._stand_alone = True
        self._plugin_spec = PluginSpec(
            config={
                "name": "RouteAddingPlugin",
                "description": "A test plugin that adds routes",
                "version": "0.1.0",
                "author": "Test Author"
            },
            path=Path(__file__).parent,
            override_settings={}
        )
        patch_plugin_spec_on_module(self)

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler_wrapper, methods=self.methods)

    async def _handler_wrapper(self, request: Request = dependency(), container: Container = dependency(), **path_params):
        self.was_called += 1
        self.received_kwargs = {**path_params, "request": request, "container": container} # For inspection

        # Call the original handler (e.g., hello_handler from the test)
        # using the per-request container. Path parameters are passed explicitly.
        # Other dependencies (like Request, ResponseBuilder) should be declared
        # in self.handler's signature with ` = dependency()` if needed.
        await container.call(self.handler, **path_params)


class EventWatcherPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.events_seen = []
        self._stand_alone = True
        self._plugin_spec = PluginSpec(
            config={
                "name": "EventWatcherPlugin",
                "description": "A test plugin that watches events",
                "version": "0.1.0",
                "author": "Test Author"
            },
            path=Path(__file__).parent,
            override_settings={}
        )
        patch_plugin_spec_on_module(self)

    async def on(self, event_name: str, **kwargs: Any) -> None:
        self.events_seen.append((event_name, kwargs))


# Example of a simple middleware for testing
# Middleware are defined as async generator factories
async def example_header_middleware(request: Request = dependency(), response: ResponseBuilder = dependency()) -> None:
    # Code here runs before the next middleware/handler
    response.add_header("X-Test-Middleware-Before", "active")
    yield
    # Code here runs after the next middleware/handler
    response.add_header("X-Test-Middleware-After", "active") 