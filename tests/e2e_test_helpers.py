"""
End-to-end testing utilities for Serv applications.

This module provides helper functions and classes for testing Serv applications
end-to-end using HTTPX AsyncClient without relying on a running server.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from httpx import ASGITransport, AsyncClient

from serv.app import App
from serv.extensions import Extension


@asynccontextmanager
async def lifespan_context(app: App) -> AsyncGenerator[None]:
    """
    Context manager that manages the lifespan protocol for an ASGI application.

    This emulates the lifespan events that would be sent by a server like Uvicorn:
    - Sends startup event and waits for completion
    - Yields control back to the caller
    - On exit, sends shutdown event and waits for completion

    Args:
        app: The Serv application instance

    Yields:
        None
    """
    receive_queue = asyncio.Queue()
    send_queue = asyncio.Queue()

    # Define async receive and send functions
    async def receive():
        return await receive_queue.get()

    async def send(message):
        await send_queue.put(message)

    # Create lifespan scope
    scope = {"type": "lifespan"}

    # Start the lifespan handler task
    lifespan_task = asyncio.create_task(app.handle_lifespan(scope, receive, send))

    try:
        # Send startup event
        await receive_queue.put({"type": "lifespan.startup"})

        # Wait for startup complete
        startup_complete = await send_queue.get()
        if startup_complete["type"] != "lifespan.startup.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.startup: {startup_complete}"
            )

        # Yield control back
        yield

    finally:
        # Send shutdown event
        await receive_queue.put({"type": "lifespan.shutdown"})

        # Wait for shutdown complete
        shutdown_complete = await send_queue.get()
        if shutdown_complete["type"] != "lifespan.shutdown.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.shutdown: {shutdown_complete}"
            )

        # Cancel the lifespan task
        lifespan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lifespan_task


class LifespanManager:
    """
    Manages the lifespan of an ASGI application by handling the protocol messages.

    This is an alternative to the lifespan_context if you need more control over
    the lifespan events, or need to implement custom handling.
    """

    def __init__(self, app: App):
        self.app = app
        self.receive_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
        self.lifespan_task = None

    async def receive(self):
        return await self.receive_queue.get()

    async def send(self, message):
        await self.send_queue.put(message)

    async def startup(self):
        """Send startup event and wait for completion."""
        # Create and start the lifespan task
        self.lifespan_task = asyncio.create_task(
            self.app.handle_lifespan({"type": "lifespan"}, self.receive, self.send)
        )

        # Send startup event
        await self.receive_queue.put({"type": "lifespan.startup"})

        # Wait for startup complete
        startup_complete = await self.send_queue.get()
        if startup_complete["type"] != "lifespan.startup.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.startup: {startup_complete}"
            )

    async def shutdown(self):
        """Send shutdown event and wait for completion."""
        if not self.lifespan_task:
            raise RuntimeError("Cannot shutdown: lifespan task not started.")

        # Send shutdown event
        await self.receive_queue.put({"type": "lifespan.shutdown"})

        # Wait for shutdown complete
        shutdown_complete = await self.send_queue.get()
        if shutdown_complete["type"] != "lifespan.shutdown.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.shutdown: {shutdown_complete}"
            )

        # Cancel the lifespan task
        self.lifespan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.lifespan_task

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None]:
        """Context manager for the lifespan protocol."""
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()


@asynccontextmanager
async def create_test_client(
    app_factory: Callable[[], App] | None = None,
    plugins: list[Extension] | None = None,
    config: dict[str, Any] | None = None,
    base_url: str = "http://testserver",
    use_lifespan: bool = False,
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test client for end-to-end testing with a fully configured App.

    This function creates an HTTPX AsyncClient configured to communicate with
    a Serv application instance. It handles the application's lifespan events
    (startup/shutdown) if requested.

    Args:
        app_factory: Optional function that returns a fully configured App instance
        plugins: Optional list of plugins to add to the app (if app_factory not provided)
        config: Optional configuration to use when creating the app (if app_factory not provided)
        base_url: Base URL to use for requests (default: "http://testserver")
        use_lifespan: Whether to use the app's lifespan context for startup/shutdown (default: False)

    Returns:
        An AsyncClient configured to communicate with the app

    Examples:
        ```python
        # Simple usage
        async with create_test_client() as client:
            response = await client.get("/")
            assert response.status_code == 200

        # With custom app factory
        def create_my_app():
            app = App(dev_mode=True)
            app.add_extension(MyExtension())
            return app

        async with create_test_client(app_factory=create_my_app) as client:
            response = await client.get("/custom-endpoint")
            assert response.status_code == 200
        ```
    """
    # Create the app if a factory wasn't provided
    if app_factory:
        app = app_factory()
    else:
        app = App(dev_mode=True)

        # Add plugins if provided
        if plugins:
            for plugin in plugins:
                app.add_extension(plugin)

        # Configure the app if configuration provided
        # This is left as a placeholder for future implementation if needed

    # Set up the transport for the client
    transport = ASGITransport(app=app)

    # Use the app's lifespan if requested
    if use_lifespan:
        lifespan_mgr = LifespanManager(app)
        async with lifespan_mgr.lifespan():
            async with AsyncClient(transport=transport, base_url=base_url) as client:
                yield client
    else:
        async with AsyncClient(transport=transport, base_url=base_url) as client:
            yield client


class AppBuilder:
    """
    Builder class for creating test applications with a fluent interface.

    This class simplifies the creation of test applications with common configuration
    patterns, making tests more readable and maintainable.

    Examples:
        ```python
        # Create a basic app with a single plugin
        app = AppBuilder().with_plugin(MyExtension()).build()

        # Create an app with multiple plugins and custom config
        app = (
            AppBuilder()
            .with_plugins([AuthExtension(), LoggingExtension()])
            .with_config({"debug": True})
            .build()
        )
        ```
    """

    def __init__(self):
        self._plugins: list[Extension] = []
        self._config: dict[str, Any] = {}
        self._dev_mode = True
        self._config_path = "./serv.config.yaml"
        self._extension_dir = "./plugins"

    def with_plugin(self, plugin: Extension) -> "AppBuilder":
        """Add a single plugin to the app."""
        self._plugins.append(plugin)
        return self

    def with_plugins(self, plugins: list[Extension]) -> "AppBuilder":
        """Add multiple plugins to the app."""
        self._plugins.extend(plugins)
        return self

    def with_config(self, config: dict[str, Any]) -> "AppBuilder":
        """Set or update configuration values."""
        self._config.update(config)
        return self

    def with_dev_mode(self, dev_mode: bool = True) -> "AppBuilder":
        """Set development mode."""
        self._dev_mode = dev_mode
        return self

    def with_config_path(self, config_path: str) -> "AppBuilder":
        """Set the configuration file path."""
        self._config_path = config_path
        return self

    def with_extension_dir(self, extension_dir: str) -> "AppBuilder":
        """Set the plugin directory."""
        self._extension_dir = extension_dir
        return self

    def build(self) -> App:
        """Build and return the configured App instance."""
        # Create the app with basic settings
        app = App(
            config=self._config_path,
            extension_dir=self._extension_dir,
            dev_mode=self._dev_mode,
        )

        # Add all plugins
        for plugin in self._plugins:
            app.add_extension(plugin)

        return app

    @asynccontextmanager
    async def build_client(
        self, base_url: str = "http://testserver", use_lifespan: bool = False
    ) -> AsyncGenerator[AsyncClient]:
        """
        Build the app and create a test client for it.

        This is a convenience method that combines build() with create_test_client().

        Args:
            base_url: Base URL to use for requests
            use_lifespan: Whether to use lifespan events (default: False)

        Returns:
            An AsyncClient configured to communicate with the app
        """
        app = self.build()
        async with create_test_client(
            app_factory=lambda: app, base_url=base_url, use_lifespan=use_lifespan
        ) as client:
            yield client
