"""
Test client utilities for Serv applications.

This module provides utilities for creating test clients that wrap Serv apps
in httpx AsyncClient instances, allowing for easy testing without running a server.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from serv._app import App
from serv.app_factory import create_app


class LifespanManager:
    """
    Manages the lifespan of an ASGI application by handling the protocol messages.

    This class handles the startup and shutdown events for an ASGI application,
    which is necessary for proper initialization of extensions and cleanup.
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
        self.lifespan_task = asyncio.create_task(
            self.app._lifecycle_manager.handle_lifespan({"type": "lifespan"}, self.receive, self.send)
        )
        await self.receive_queue.put({"type": "lifespan.startup"})
        startup_complete = await self.send_queue.get()
        if startup_complete["type"] != "lifespan.startup.complete":
            raise RuntimeError(
                f"Unexpected response to lifespan.startup: {startup_complete}"
            )

    async def shutdown(self):
        """Send shutdown event and wait for completion."""
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
        """Context manager for the lifespan protocol."""
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()


@asynccontextmanager
async def create_test_app_client(
    config_path: Path | str,
    *,
    app_module_str: str | None = None,
    extension_dirs: str | None = None,
    dev: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    no_reload: bool = False,
    workers: int = 1,
    factory: bool = False,
    dry_run: bool = False,
    base_url: str = "http://testserver",
    use_lifespan: bool = True,
    timeout: float = 5.0,
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test client that wraps a Serv app in an httpx AsyncClient.

    This function creates an App instance using the same configuration options
    as the CLI's 'serv launch' command, then wraps it in an httpx AsyncClient
    for testing without needing to start a server.

    Args:
        config_path: Path to the config file to use (equivalent to --config)
        app_module_str: Custom application class in format "module.path:ClassName" (equivalent to --app)
        extension_dirs: Directory to search for extensions (equivalent to --extension-dirs)
        dev: Enable development mode (equivalent to --dev)
        host: Host binding (equivalent to --host, used only for dry_run info)
        port: Port binding (equivalent to --port, used only for dry_run info)
        reload: Enable auto-reload (equivalent to --reload, used only for dry_run info)
        no_reload: Disable auto-reload (equivalent to --no-reload, used only for dry_run info)
        workers: Number of workers (equivalent to --workers, used only for dry_run info)
        factory: Treat app_module_str as factory (equivalent to --factory, used only for dry_run info)
        dry_run: If True, just create app but don't return client (equivalent to --dry-run)
        base_url: Base URL for test requests
        use_lifespan: Whether to handle app lifespan events
        timeout: Request timeout in seconds

    Returns:
        An AsyncClient configured to communicate with the app

    Raises:
        Exception: If app creation fails

    Examples:
        Basic usage:
        ```python
        from pathlib import Path
        from serv import create_test_app_client

        async with create_test_app_client(Path("serv.config.yaml")) as client:
            response = await client.get("/")
            assert response.status_code == 200
        ```

        With development mode:
        ```python
        async with create_test_app_client(
            Path("serv.config.yaml"),
            dev=True
        ) as client:
            response = await client.get("/debug")
            assert response.status_code == 200
        ```

        With custom extension directory:
        ```python
        async with create_test_app_client(
            Path("serv.config.yaml"),
            extension_dirs="./custom_extensions"
        ) as client:
            response = await client.get("/custom-endpoint")
            assert response.status_code == 200
        ```

        Testing a specific endpoint:
        ```python
        async def test_api_endpoint():
            async with create_test_app_client(Path("test.config.yaml")) as client:
                # Test POST request
                response = await client.post("/api/users", json={"name": "Test User"})
                assert response.status_code == 201

                # Test GET request
                response = await client.get("/api/users/1")
                assert response.status_code == 200
                user = response.json()
                assert user["name"] == "Test User"
        ```
    """
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Convert Path to string if needed
    config_str = str(config_path) if isinstance(config_path, Path) else config_path

    # Create the app using the same logic as the CLI
    app = create_app(
        app_module_str=app_module_str,
        config=config_str,
        extension_dirs=extension_dirs,
        dev=dev,
    )

    # Handle dry run mode
    if dry_run:
        print("=== Dry Run Mode ===")
        print("Application loaded successfully. Server would start with:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Dev Mode: {dev}")
        if dev:
            reload_enabled = not no_reload
            print(f"  Reload: {reload_enabled}")
        else:
            print(f"  Reload: {reload}")
        print(f"  Workers: {workers}")
        # For dry run, we don't yield a client
        yield None
        return

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
