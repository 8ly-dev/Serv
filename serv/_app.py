import asyncio
import contextlib
import logging
import sys
from asyncio import Task, get_running_loop
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from itertools import chain
from pathlib import Path
from typing import Any

from asgiref.typing import (
    ASGIReceiveCallable as Receive,
)
from asgiref.typing import (
    ASGISendCallable as Send,
)
from asgiref.typing import (
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
    Scope,
)
from bevy import Inject, get_registry, injectable
from bevy.containers import Container

from serv._routing import Router
from serv.app.middleware import MiddlewareManager
from serv.config import load_raw_config
from serv.database import DatabaseManager
from serv.extensions import Listener
from serv.extensions.importer import Importer
from serv.extensions.loader import ExtensionLoader
from serv.injectors import inject_request_object, inject_websocket_object
from serv.protocols import AppContextProtocol, EventEmitterProtocol, RouterProtocol
from serv.requests import Request
from serv.responses import ResponseBuilder

logger = logging.getLogger(__name__)

# Test comment for pre-commit hooks


class EventEmitter:
    """Event emission system for extension communication.

    The EventEmitter manages the broadcasting of events to all registered listeners
    in the application. It provides both synchronous and asynchronous event emission
    capabilities, allowing listeners to respond to application lifecycle events and
    custom events.

    Examples:
        Basic event emission:

        ```python
        # Emit an event to all listeners
        await app.emit("user_created", user_id=123, email="user@example.com")

        # Emit from within a route handler
        task = app.emit("order_processed", order_id=456)
        ```

        Listener responding to events:

        ```python
        class NotificationListener(Listener):
            async def on_user_created(self, user_id: int, email: str):
                await self.send_welcome_email(email)

            async def on_order_processed(self, order_id: int):
                await self.update_inventory(order_id)
        ```

    Args:
        extensions: Dictionary mapping extension paths to lists of listener instances.
    """

    def __init__(self, extensions: dict[Path, list[Listener]]):
        self.extensions = extensions

    @injectable
    def emit_sync(self, event: str, *, container: Inject[Container], **kwargs) -> Task:
        return get_running_loop().create_task(
            self.emit(event, container=container, **kwargs)
        )

    @injectable
    async def emit(self, event: str, *, container: Inject[Container], **kwargs):
        async with asyncio.TaskGroup() as tg:
            for extension in chain(*self.extensions.values()):
                tg.create_task(
                    container.call(extension.on, event, container=container, **kwargs)
                )


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
        self._extensions: dict[Path, list[Listener]] = defaultdict(list)

        # Initialize the extension loader
        self._extension_loader_instance = ExtensionLoader(self, self._extension_loader)

        self._emit = EventEmitter(self._extensions)

        # Initialize database manager
        self._database_manager = DatabaseManager(self._config, self._container)

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
        if not loaded_extensions and not loaded_middleware:
            self._enable_welcome_extension()

    def _init_container(self):
        # Note: We intentionally do NOT register the type_factory hook
        # to prevent auto-creation of objects like Request and ResponseBuilder

        # Register hooks for injection
        inject_request_object.register_hook(self._registry)

        # Register WebSocket injection hook
        inject_websocket_object.register_hook(self._registry)

        # Set up container instances
        self._container.add(App, self)
        self._container.add(EventEmitter, self._emit)

        # Register protocol implementations using instances dict for protocols
        self._container.instances[EventEmitterProtocol] = self._emit
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
        if hasattr(extension, "__extension_spec__") and extension.__extension_spec__:
            spec = extension.__extension_spec__
        elif hasattr(extension, "_stand_alone") and extension._stand_alone:
            # For stand-alone listeners, use a default path
            spec = type("MockSpec", (), {"path": Path("__stand_alone__")})()
        else:
            module = sys.modules[extension.__module__]
            spec = module.__extension_spec__

        self._extensions[spec.path].append(extension)
        self._container.add(extension)

    def get_extension(self, path: Path) -> Listener | None:
        return self._extensions.get(path, [None])[0]

    def _load_extensions(self, extensions_config: list[dict[str, Any]]):
        """Legacy method, delegates to _init_extensions."""
        return self._init_extensions(extensions_config)

    def _enable_welcome_extension(self):
        """Enable the bundled welcome extension if no other extensions are registered."""
        extension_spec, exceptions = self._extension_loader_instance.load_extension(
            "serv.bundled.extensions.welcome"
        )
        if exceptions:
            raise ExceptionGroup(
                "Exceptions raised while loading welcome extension", exceptions
            )

        return True

    # Backward compatibility methods removed - use ExtensionLoader directly

    # Extension loading methods removed - extensions are now loaded via configuration
    # Use the extensions: key in serv.config.yaml to specify extensions to load

    @injectable
    def emit_sync(self, event: str, *, container: Inject[Container], **kwargs) -> Task:
        return self._emit.emit_sync(event, container=container, **kwargs)

    @injectable
    async def emit(self, event: str, *, container: Inject[Container], **kwargs) -> None:
        """Async emit method for EventEmitterProtocol compliance."""
        await self._emit.emit(event, container=container, **kwargs)

    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        async for event in self._lifespan_iterator(receive):
            match event:
                case {"type": "lifespan.startup"}:
                    logger.debug("Lifespan startup event")
                    # Initialize databases before emitting startup event
                    await self._database_manager.initialize_databases()
                    await self.emit(
                        "app.startup", scope=scope, container=self._container
                    )
                    await send(
                        LifespanStartupCompleteEvent(type="lifespan.startup.complete")
                    )

                case {"type": "lifespan.shutdown"}:
                    logger.debug("Lifespan shutdown event")
                    await send(
                        LifespanShutdownCompleteEvent(type="lifespan.shutdown.complete")
                    )
                    await self.emit(
                        "app.shutdown", scope=scope, container=self._container
                    )
                    # Shutdown databases before exit stack cleanup
                    await self._database_manager.shutdown_databases()
                    await self._async_exit_stack.aclose()

    async def _lifespan_iterator(self, receive: Receive):
        event = {}
        while event.get("type") != "lifespan.shutdown":
            event = await receive()
            yield event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope["type"]:
            case "lifespan":
                await self.handle_lifespan(scope, receive, send)
            case "http":
                await self._handle_request(scope, receive, send)
            case "websocket":
                await self._handle_websocket(scope, receive, send)
            case _:
                logger.warning(f"Unsupported ASGI scope type: {scope['type']}")

    async def _handle_request(self, scope: Scope, receive: Receive, send: Send):
        with self._container.branch() as container:
            request = Request(scope, receive)
            response_builder = ResponseBuilder(send)
            router_instance_for_request = Router()

            container.add(Request, request)
            container.add(ResponseBuilder, response_builder)
            container.add(Container, container)
            container.add(Router, router_instance_for_request)
            # Register router for protocol-based access
            container.instances[RouterProtocol] = router_instance_for_request

            error_to_propagate = None
            try:
                # Pass the newly created router_instance to the event
                await self.emit("app.request.begin", container=container)

                # Run middleware stack
                try:
                    await self._middleware_manager.run_middleware_stack(
                        container=container,
                        request_instance=request,
                        emit_callback=self.emit,
                    )
                except Exception as e:
                    error_to_propagate = e

                # Handle any errors that occurred
                if error_to_propagate:
                    await self._middleware_manager.run_error_handler(
                        error_to_propagate, container=container
                    )

                await self.emit(
                    "app.request.end", error=error_to_propagate, container=container
                )

            except Exception as e:
                logger.exception(
                    "Unhandled exception during request processing", exc_info=e
                )
                await self._middleware_manager.run_error_handler(e, container=container)
                await self.emit("app.request.end", error=e, container=container)

            finally:
                # Ensure response is sent. ResponseBuilder.send_response() should be robust
                # enough to handle being called if headers were already sent by an error handler,
                # or to send a default response if nothing was set.
                # Ensure response is sent
                try:
                    await response_builder.send_response()
                except Exception as final_send_exc:
                    logger.error(
                        "Exception during final send_response", exc_info=final_send_exc
                    )

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send):
        """Handle WebSocket connections."""
        with self._container.branch() as container:
            router_instance_for_request = Router()
            container.add(Container, container)
            container.add(Router, router_instance_for_request)
            # Register router for protocol-based access
            container.instances[RouterProtocol] = router_instance_for_request

            try:
                # Emit websocket connection begin event
                await container.call(self._emit.emit, "app.websocket.begin")

                # Find the WebSocket route handler
                resolved_route_info = router_instance_for_request.resolve_websocket(
                    scope.get("path", "/")
                )

                if not resolved_route_info:
                    # No WebSocket route found, reject connection
                    await send({"type": "websocket.close", "code": 4404})
                    return

                handler_callable, path_params, route_settings = resolved_route_info

                # Extract WebSocket frame type from handler annotations if present
                from typing import get_args, get_origin, get_type_hints

                from serv.websocket import FrameType, WebSocket

                frame_type = FrameType.TEXT  # Default frame type

                try:
                    # Get type hints for the handler
                    type_hints = get_type_hints(handler_callable, include_extras=True)

                    # Look for WebSocket parameter with frame type annotation
                    for _param_name, param_type in type_hints.items():
                        if get_origin(param_type) is not None:
                            # Check if it's Annotated[WebSocket, FrameType.X]
                            origin = get_origin(param_type)
                            if origin is type(
                                type_hints.get("__annotated__", type(None))
                            ):  # Annotated type
                                args = get_args(param_type)
                                if len(args) >= 2 and args[0] is WebSocket:
                                    # Found WebSocket parameter, check for FrameType in annotations
                                    for annotation in args[1:]:
                                        if isinstance(annotation, FrameType):
                                            frame_type = annotation
                                            break
                            elif param_type is WebSocket:
                                # Plain WebSocket parameter, use default frame type
                                break
                except Exception as e:
                    # If annotation parsing fails, use default frame type
                    logger.debug(f"Could not parse WebSocket annotations: {e}")

                # Create WebSocket instance
                websocket = WebSocket(scope, receive, send, frame_type)

                # Create a branch of the container with route settings and WebSocket instance
                with container.branch() as route_container:
                    from serv._routing import RouteSettings

                    route_container.add(RouteSettings, RouteSettings(**route_settings))
                    route_container.add(WebSocket, websocket)

                    try:
                        # Call the WebSocket handler
                        await route_container.call(handler_callable, **path_params)
                    except Exception as e:
                        logger.exception(f"WebSocket handler error: {e}")
                        # Close connection with error code
                        if websocket.is_connected:
                            await websocket.close(
                                code=1011, reason="Internal server error"
                            )

                await container.call(self._emit.emit, "app.websocket.end")

            except Exception as e:
                logger.exception(
                    f"Unhandled exception during WebSocket processing: {e}"
                )
                # Attempt to close connection gracefully
                try:
                    await send({"type": "websocket.close", "code": 1011})
                except Exception:
                    pass  # Connection may already be closed

                await container.call(self._emit.emit, "app.websocket.end", error=e)
