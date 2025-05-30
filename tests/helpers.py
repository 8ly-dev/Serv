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

from serv.extensions import Listener, on
from serv.extensions.importer import Importer
from serv.extensions.loader import ExtensionSpec
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routing import Router


def patch_extension_spec_on_module(extension: Listener):
    """Patch the extension's module with its __extension_spec__ for testing.

    This is needed because test extensions are standalone and don't go through
    the normal extension loading system that sets module.__extension_spec__.
    """
    if hasattr(extension, "_extension_spec"):
        module = sys.modules[extension.__module__]
        module.__extension_spec__ = extension._extension_spec
        module.__extension_spec__ = extension._extension_spec  # Backward compatibility


class RouteAddingExtension(Listener):
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
        # Define _extension_spec and patch module BEFORE super().__init__
        self._extension_spec = ExtensionSpec(
            config={
                "name": "RouteAddingExtension",
                "description": "A test plugin that adds routes",
                "version": "0.1.0",
                "author": "Test Author",
            },
            path=Path(__file__).parent,
            override_settings={},
            importer=create_mock_importer(Path(__file__).parent),
        )
        patch_extension_spec_on_module(self)
        super().__init__()
        # self._stand_alone = True # No longer needed here for Extension base class init

    @on("app.request.begin")
    async def add_route(self, router: Router = dependency()) -> None:
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


def create_test_extension_spec(
    name: str = "TestExtension",
    version: str = "0.1.0",
    path: Path = None,
    override_settings: dict[str, Any] = None,
    importer: Importer = None,
) -> ExtensionSpec:
    """Create an ExtensionSpec for testing purposes."""
    if path is None:
        path = Path(".")
    if override_settings is None:
        override_settings = {}
    if importer is None:
        importer = create_mock_importer(path)

    config = {
        "name": name,
        "version": version,
        "description": "A test extension",
        "author": "Test Author",
    }

    return ExtensionSpec(
        config=config, path=path, override_settings=override_settings, importer=importer
    )


# Backward compatibility aliases
patch_extension_spec_on_module = patch_extension_spec_on_module


class EventWatcherExtension(Listener):
    def __init__(self):
        self.events_seen = []
        # Define _extension_spec and patch module BEFORE super().__init__
        self._extension_spec = create_test_extension_spec(
            name="EventWatcherExtension", path=Path(__file__).parent
        )
        patch_extension_spec_on_module(self)
        super().__init__()
        # self._stand_alone = True # No longer needed here for Extension base class init

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
