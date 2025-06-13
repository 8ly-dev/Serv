import contextlib
import logging
from asyncio import Task
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from asgiref.typing import (
    ASGIReceiveCallable as Receive,
)
from asgiref.typing import (
    ASGISendCallable as Send,
)
from asgiref.typing import (
    Scope,
)
from bevy import Inject, get_registry, injectable
from bevy.containers import Container

from serv.app.extensions import ExtensionManager
from serv.app.lifecycle import EventEmitter, LifecycleManager
from serv.app.middleware import MiddlewareManager
from serv.config import load_raw_config
from serv.database import DatabaseManager
from serv.extensions import Listener
from serv.extensions.importer import Importer
from serv.extensions.loader import ExtensionLoader
from serv.injectors import inject_request_object, inject_websocket_object
from serv.protocols import AppContextProtocol, EventEmitterProtocol

logger = logging.getLogger(__name__)

# Test comment for pre-commit hooks


class App(EventEmitterProtocol, AppContextProtocol):
    """The main ASGI application class for Serv web framework.

    This class serves as the central orchestrator for your web application, handling
    incoming HTTP requests, managing extensions, middleware, routing, and dependency injection.
    It implements the ASGI (Asynchronous Server Gateway Interface) specification.

    The App class provides:
    - Extension system for extensible functionality
    - Middleware stack for request/response processing
    - Dependency injection container
    - Error handling and custom error pages
    - Template rendering capabilities
    - Event emission system for extension communication

    Examples:
        Basic application setup:

        ```python
        from serv import App

        # Create a basic app
        app = App()

        # Create app with custom config
        app = App(config="./config/production.yaml")

        # Create app with custom extension directory
        app = App(extension_dir="./my_extensions")

        # Development mode with enhanced debugging
        app = App(dev_mode=True)
        ```

        Using with ASGI servers:

        ```python
        # For uvicorn
        # uvicorn main:app --reload

        # For gunicorn
        # gunicorn main:app -k uvicorn.workers.UvicornWorker
        ```

        Advanced configuration:

        ```python
        app = App(
            config="./config/production.yaml",
            extension_dir="./extensions",
            dev_mode=False
        )

        # Add custom error handler
        async def custom_404_handler(error):
            # Handle 404 errors
            pass

        app.add_error_handler(HTTPNotFoundException, custom_404_handler)

        # Add middleware
        async def logging_middleware():
            # Middleware logic
            yield

        app.add_middleware(logging_middleware)
        ```
    """

    def __init__(
        self,
        *,
        config: str = "./serv.config.yaml",
        extension_dir: str = "./extensions",
        dev_mode: bool = False,
    ):
        """Initialize a new Serv application instance.

        Creates and configures a new ASGI application with the specified settings.
        This includes setting up the dependency injection container, loading extensions,
        configuring middleware, and preparing the routing system.

        Args:
            config: Path to the YAML configuration file. The config file defines
                site information, enabled extensions, middleware stack, and other
                application settings. Defaults to "./serv.config.yaml".
            extension_dir: Directory path where extensions are located. Extensions in this
                directory will be available for loading. Defaults to "./extensions".
            extension_dir: Legacy parameter name for extension_dir (backward compatibility).
            dev_mode: Enable development mode features including enhanced error
                reporting, debug logging, and development-specific behaviors.
                Should be False in production. Defaults to False.

        Raises:
            ServConfigError: If the configuration file cannot be loaded or contains
                invalid YAML/configuration structure.
            ImportError: If required dependencies for extensions cannot be imported.
            ValueError: If extension_dir path is invalid or inaccessible.

        Examples:
            Basic initialization:

            ```python
            # Use default settings
            app = App()

            # Custom config file
            app = App(config="config/production.yaml")

            # Custom extension directory
            app = App(extension_dir="src/extensions")

            # Development mode
            app = App(dev_mode=True)
            ```

            Production setup:

            ```python
            app = App(
                config="/etc/myapp/config.yaml",
                extension_dir="/opt/myapp/extensions",
                dev_mode=False
            )
            ```

            Development setup:

            ```python
            app = App(
                config="dev.config.yaml",
                extension_dir="./dev_extensions",
                dev_mode=True
            )
            ```

        Note:
            The application will automatically load the welcome extension if no other
            extensions are configured, providing a default landing page for new projects.
        """
        self._config = self._load_config(config)
        self._dev_mode = dev_mode
        self._registry = get_registry()
        self._container = self._registry.create_container()
        self._async_exit_stack = contextlib.AsyncExitStack()

        # Initialize middleware manager
        self._middleware_manager = MiddlewareManager(dev_mode=dev_mode)

        # Handle backward compatibility for extension_dir parameter
        actual_extension_dir = extension_dir if extension_dir is None else extension_dir
        self._extension_loader = Importer(actual_extension_dir)

        # Initialize extension manager
        self._extension_manager = ExtensionManager()

        # Initialize the extension loader
        self._extension_loader_instance = ExtensionLoader(self, self._extension_loader)

        # Initialize database manager
        self._database_manager = DatabaseManager(self._config, self._container)

        # Initialize lifecycle manager
        self._lifecycle_manager = LifecycleManager(
            extension_manager=self._extension_manager,
            middleware_manager=self._middleware_manager,
            database_manager=self._database_manager,
            container=self._container,
            async_exit_stack=self._async_exit_stack,
        )

        self._init_container()
        self._init_extensions(
            self._config.get("extensions", self._config.get("extensions", []))
        )

    def _load_config(self, config_path: str) -> dict[str, Any]:
        return load_raw_config(config_path)

    def _init_extensions(self, extensions_config: list[dict[str, Any]]):
        loaded_extensions, loaded_middleware = (
            self._extension_loader_instance.load_extensions(extensions_config)
        )
        # Use extension manager to handle welcome extension loading
        self._extension_manager.load_welcome_extension_if_needed(
            self._extension_loader_instance, loaded_extensions, loaded_middleware
        )

    def _init_container(self):
        # Note: We intentionally do NOT register the type_factory hook
        # to prevent auto-creation of objects like Request and ResponseBuilder

        # Register hooks for injection
        inject_request_object.register_hook(self._registry)

        # Register WebSocket injection hook
        inject_websocket_object.register_hook(self._registry)

        # Set up container instances
        self._container.add(App, self)
        self._container.add(EventEmitter, self._lifecycle_manager.event_emitter)

        # Register protocol implementations using instances dict for protocols
        self._container.instances[EventEmitterProtocol] = self._lifecycle_manager.event_emitter
        self._container.instances[AppContextProtocol] = self

    @property
    def dev_mode(self) -> bool:
        """Get the current development mode setting."""
        return self._dev_mode

    @dev_mode.setter
    def dev_mode(self, value: bool) -> None:
        """Set the development mode setting."""
        self._dev_mode = value
        # Keep middleware manager in sync
        self._middleware_manager.dev_mode = value

    def on_shutdown(self, callback: Callable[[], Awaitable[None]]):
        """Add a callback to be called when the application is shutting down."""
        self._async_exit_stack.push_async_callback(callback)

    def add_error_handler(
        self,
        error_type: type[Exception],
        handler: Callable[[Exception], Awaitable[None]],
    ):
        """Register a custom error handler for specific exception types.

        Error handlers allow you to customize how your application responds to
        different types of errors, providing custom error pages, logging, or
        recovery mechanisms.

        Args:
            error_type: The exception class to handle. The handler will be called
                for this exception type and any of its subclasses.
            handler: An async function that will be called when the exception occurs.
                The handler receives the exception instance and can use dependency
                injection to access request/response objects.

        Examples:
            Handle 404 errors with a custom page:

            ```python
            from serv.exceptions import HTTPNotFoundException
            from serv.responses import ResponseBuilder
            from bevy import injectable, Inject

            @injectable
            async def custom_404_handler(
                error: HTTPNotFoundException,
                response: Inject[ResponseBuilder]
            ):
                response.set_status(404)
                response.content_type("text/html")
                response.body("<h1>Page Not Found</h1><p>Sorry, that page doesn't exist.</p>")

            app.add_error_handler(HTTPNotFoundException, custom_404_handler)
            ```

            Handle validation errors:

            ```python
            class ValidationError(Exception):
                def __init__(self, message: str, field: str):
                    self.message = message
                    self.field = field

            @injectable
            async def validation_error_handler(
                error: ValidationError,
                response: Inject[ResponseBuilder]
            ):
                response.set_status(400)
                response.content_type("application/json")
                response.body({
                    "error": "validation_failed",
                    "message": error.message,
                    "field": error.field
                })

            app.add_error_handler(ValidationError, validation_error_handler)
            ```

            Generic error handler with logging:

            ```python
            import logging

            @injectable
            async def generic_error_handler(
                error: Exception,
                response: Inject[ResponseBuilder],
                request: Inject[Request]
            ):
                logging.error(f"Unhandled error on {request.path}: {error}")
                response.set_status(500)
                response.content_type("text/html")
                response.body("<h1>Internal Server Error</h1>")

            app.add_error_handler(Exception, generic_error_handler)
            ```
        """
        self._middleware_manager.add_error_handler(error_type, handler)

    def add_middleware(self, middleware: Callable[[], AsyncIterator[None]]):
        """Add middleware to the application's middleware stack.

        Middleware functions are executed in the order they are added, wrapping
        around the request handling process. They can modify requests, responses,
        add headers, implement authentication, logging, and more.

        Args:
            middleware: An async generator function that yields control to the next
                middleware or route handler. The function should yield exactly once.

        Examples:
            Basic logging middleware:

            ```python
            import logging
            from serv.requests import Request
            from bevy import injectable, Inject

            @injectable
            async def logging_middleware(
                request: Inject[Request]
            ):
                logging.info(f"Request: {request.method} {request.path}")
                start_time = time.time()

                yield  # Pass control to next middleware/handler

                duration = time.time() - start_time
                logging.info(f"Response time: {duration:.3f}s")

            app.add_middleware(logging_middleware)
            ```

            Authentication middleware:

            ```python
            from serv.responses import ResponseBuilder
            from serv.requests import Request
            from bevy import injectable, Inject

            @injectable
            async def auth_middleware(
                request: Inject[Request],
                response: Inject[ResponseBuilder]
            ):
                # Check for authentication
                auth_header = request.headers.get("authorization")
                if not auth_header and request.path.startswith("/api/"):
                    response.set_status(401)
                    response.content_type("application/json")
                    response.body({"error": "Authentication required"})
                    return  # Don't yield, stop processing

                yield  # Continue to next middleware/handler

            app.add_middleware(auth_middleware)
            ```

            CORS middleware:

            ```python
            @injectable
            async def cors_middleware(
                request: Inject[Request],
                response: Inject[ResponseBuilder]
            ):
                # Add CORS headers
                response.add_header("Access-Control-Allow-Origin", "*")
                response.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
                response.add_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

                # Handle preflight requests
                if request.method == "OPTIONS":
                    response.set_status(200)
                    return

                yield  # Continue processing

            app.add_middleware(cors_middleware)
            ```

        Note:
            Middleware is executed in LIFO (Last In, First Out) order during request
            processing, and FIFO (First In, First Out) order during response processing.
        """
        self._middleware_manager.add_middleware(middleware)

    def add_extension(self, extension: Listener):
        """Register an extension with the application.

        This method delegates to the ExtensionManager for consistent
        extension handling and registration with the DI container.
        """
        self._extension_manager.add_extension(extension, self._container)

    def get_extension(self, path: Path) -> Listener | None:
        """Retrieve an extension by its filesystem path.

        This method delegates to the ExtensionManager for consistent
        extension retrieval.
        """
        return self._extension_manager.get_extension(path)

    def _load_extensions(self, extensions_config: list[dict[str, Any]]):
        """Legacy method, delegates to _init_extensions."""
        return self._init_extensions(extensions_config)

    def _enable_welcome_extension(self):
        """Legacy method - now handled by ExtensionManager."""
        return self._extension_manager.load_welcome_extension_if_needed(
            self._extension_loader_instance, [], []
        )

    # Backward compatibility methods removed - use ExtensionLoader directly

    # Extension loading methods removed - extensions are now loaded via configuration
    # Use the extensions: key in serv.config.yaml to specify extensions to load

    @injectable
    def emit_sync(self, event: str, *, container: Inject[Container], **kwargs) -> Task:
        """Emit an event synchronously, returning a task.
        
        Delegates to the LifecycleManager's event emission system.
        """
        return self._lifecycle_manager.emit_sync(event, container=container, **kwargs)

    @injectable
    async def emit(self, event: str, *, container: Inject[Container], **kwargs) -> None:
        """Emit an event asynchronously, waiting for all listeners.
        
        Delegates to the LifecycleManager's event emission system.
        """
        await self._lifecycle_manager.emit(event, container=container, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI application entry point.
        
        Delegates to the LifecycleManager for request processing.
        """
        await self._lifecycle_manager(scope, receive, send)
