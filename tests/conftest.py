import asyncio  # Import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient  # Import ASGITransport

from serv.app import App
from serv.extensions import Extension
from tests.e2e.helpers import AppBuilder


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app() -> App:
    """Create a test app instance."""
    return App(dev_mode=True)


class LifespanManager:
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
        self.lifespan_task = asyncio.create_task(
            self.app.handle_lifespan({"type": "lifespan"}, self.receive, self.send)
        )
        await self.receive_queue.put({"type": "lifespan.startup"})
        startup_complete = await self.send_queue.get()
        if startup_complete["type"] != "lifespan.startup.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.startup: {startup_complete}"
            )

    async def shutdown(self):
        if not self.lifespan_task:
            raise RuntimeError("Cannot shutdown: lifespan task not started.")
        await self.receive_queue.put({"type": "lifespan.shutdown"})
        shutdown_complete = await self.send_queue.get()
        if shutdown_complete["type"] != "lifespan.shutdown.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.shutdown: {shutdown_complete}"
            )
        self.lifespan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.lifespan_task

    @asynccontextmanager
    async def lifespan(self):
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()


@pytest_asyncio.fixture
async def client(app: App) -> AsyncClient:
    """Legacy client fixture using the basic app instance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", timeout=1.0
    ) as c:
        yield c


@asynccontextmanager
async def create_test_client(
    app_factory: Callable[[], App] = None,
    plugins: list[Extension] = None,
    config: dict[str, Any] = None,
    base_url: str = "http://testserver",
    use_lifespan: bool = True,
    timeout: float = 5.0,
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test client for end-to-end testing with a fully configured App.

    Args:
        app_factory: Optional function that returns a fully configured App instance
        plugins: Optional list of plugins to add to the app (if app_factory not provided)
        config: Optional configuration to use when creating the app (if app_factory not provided)
        base_url: Base URL to use for requests (default: "http://testserver")
        use_lifespan: Whether to use the app's lifespan context for startup/shutdown (default: True)
        timeout: Request timeout in seconds (default: 5.0)

    Returns:
        An AsyncClient configured to communicate with the app
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
            async with AsyncClient(
                transport=transport, base_url=base_url, timeout=timeout
            ) as client:
                yield client
    else:
        async with AsyncClient(
            transport=transport, base_url=base_url, timeout=timeout
        ) as client:
            yield client


@pytest_asyncio.fixture
async def app_test_client():
    """
    Fixture that returns the create_test_client function.

    This allows tests to create test clients with custom app configurations.

    Usage:
        ```
        @pytest.mark.asyncio
        async def test_custom_app(app_test_client):
            async with app_test_client(plugins=[MyExtension()]) as client:
                response = await client.get("/my-endpoint")
                assert response.status_code == 200
        ```
    """
    return create_test_client


@pytest.fixture
def app_builder():
    """
    Fixture that returns a AppBuilder instance.

    This allows tests to create customized app instances with a fluent interface.

    Usage:
        ```
        @pytest.mark.asyncio
        async def test_with_builder(app_builder):
            builder = app_builder.with_plugin(MyExtension())

            # Use as a factory for app instance
            app = builder.build()

            # Or directly as a test client
            async with builder.build_client() as client:
                response = await client.get("/my-endpoint")
                assert response.status_code == 200
        ```
    """
    return AppBuilder()


@pytest.fixture(autouse=True)
def mock_find_extension_spec():
    """Mock find_extension_spec to prevent hanging during Route tests."""
    with (
        patch("serv.extensions.loader.find_extension_spec", return_value=None),
        patch("serv.app.App._enable_welcome_extension"),
    ):
        yield
