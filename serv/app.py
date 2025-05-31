import asyncio
import contextlib
import json
import logging
import sys
import traceback
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
from bevy import dependency, get_registry, inject
from bevy.containers import Container
from jinja2 import Environment, FileSystemLoader

from serv.config import load_raw_config
from serv.exceptions import HTTPMethodNotAllowedException, ServException
from serv.extensions import Listener
from serv.extensions.importer import Importer
from serv.extensions.loader import ExtensionLoader
from serv.injectors import inject_request_object, inject_websocket_object
from serv.requests import Request
from serv.responses import ResponseBuilder
from serv.routing import HTTPNotFoundException, Router

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

    @inject
    def emit_sync(
        self, event: str, *, container: Container = dependency(), **kwargs
    ) -> Task:
        return get_running_loop().create_task(
            self.emit(event, container=container, **kwargs)
        )

    @inject
    async def emit(self, event: str, *, container: Container = dependency(), **kwargs):
        async with asyncio.TaskGroup() as tg:
            for extension in chain(*self.extensions.values()):
                tg.create_task(
                    container.call(extension.on, event, container=container, **kwargs)
                )


class App:
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
        self._error_handlers: dict[
            type[Exception], Callable[[Exception], Awaitable[None]]
        ] = {}
        self._middleware = []

        # Handle backward compatibility for extension_dir parameter
        actual_extension_dir = extension_dir if extension_dir is None else extension_dir
        self._extension_loader = Importer(actual_extension_dir)
        self._extensions: dict[Path, list[Listener]] = defaultdict(list)

        # Initialize the extension loader
        self._extension_loader_instance = ExtensionLoader(self, self._extension_loader)

        self._emit = EventEmitter(self._extensions)

        self._init_container()
        self._register_default_error_handlers()
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
        # Register hooks for injection
        inject_request_object.register_hook(self._registry)
        
        # Register WebSocket injection hook
        inject_websocket_object.register_hook(self._registry)

        # Set up container instances
        self._container.add(App, self)
        self._container.add(EventEmitter, self._emit)

    def _register_default_error_handlers(self):
        self.add_error_handler(HTTPNotFoundException, self._default_404_handler)
        self.add_error_handler(HTTPMethodNotAllowedException, self._default_405_handler)

    @property
    def dev_mode(self) -> bool:
        """Get the current development mode setting."""
        return self._dev_mode

    @dev_mode.setter
    def dev_mode(self, value: bool) -> None:
        """Set the development mode setting."""
        self._dev_mode = value

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
            from bevy import dependency

            async def custom_404_handler(
                error: HTTPNotFoundException,
                response: ResponseBuilder = dependency()
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

            async def validation_error_handler(
                error: ValidationError,
                response: ResponseBuilder = dependency()
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

            async def generic_error_handler(
                error: Exception,
                response: ResponseBuilder = dependency(),
                request: Request = dependency()
            ):
                logging.error(f"Unhandled error on {request.path}: {error}")
                response.set_status(500)
                response.content_type("text/html")
                response.body("<h1>Internal Server Error</h1>")

            app.add_error_handler(Exception, generic_error_handler)
            ```
        """
        self._error_handlers[error_type] = handler

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
            from bevy import dependency

            async def logging_middleware(
                request: Request = dependency()
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
            from bevy import dependency

            async def auth_middleware(
                request: Request = dependency(),
                response: ResponseBuilder = dependency()
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
            async def cors_middleware(
                request: Request = dependency(),
                response: ResponseBuilder = dependency()
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
        self._middleware.append(middleware)

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

    def emit(
        self, event: str, *, container: Container = dependency(), **kwargs
    ) -> Task:
        return self._emit.emit_sync(event, container=container, **kwargs)

    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        async for event in self._lifespan_iterator(receive):
            match event:
                case {"type": "lifespan.startup"}:
                    logger.debug("Lifespan startup event")
                    await self.emit(
                        "app.startup", scope=scope, container=self._container
                    )
                    await send(
                        LifespanStartupCompleteEvent(type="lifespan.startup.complete")
                    )

                case {"type": "lifespan.shutdown"}:
                    logger.debug("Lifespan shutdown event")
                    await self.emit(
                        "app.shutdown", scope=scope, container=self._container
                    )
                    await self._async_exit_stack.aclose()
                    await send(
                        LifespanShutdownCompleteEvent(type="lifespan.shutdown.complete")
                    )

    def _get_template_locations(self) -> list[Path]:
        """Get the template locations for this app.

        Returns a list of paths to search for templates.
        """
        return [Path.cwd() / "templates", Path(__file__).parent / "templates"]

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context.

        Args:
            template_name: Name of the template to render
            context: Context to render the template with

        Returns:
            Rendered template as a string
        """
        template_locations = self._get_template_locations()
        env = Environment(loader=FileSystemLoader(template_locations))

        # Try to load the template
        try:
            template = env.get_template(template_name)
        except Exception:
            logger.exception(f"Failed to load template {template_name}")
            # Special case for error templates - provide a fallback
            if template_name.startswith("error/"):
                status_code = context.get("status_code", 500)
                error_title = context.get("error_title", "Error")
                error_message = context.get("error_message", "An error occurred")

                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{status_code} {error_title}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; }}
                        h1 {{ color: #d00; }}
                        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <h1>{status_code} {error_title}</h1>
                    <p>{error_message}</p>
                </body>
                </html>
                """
            raise

        # Render the template
        return template.render(**context)

    @inject
    async def _default_error_handler(
        self,
        error: Exception,
        response: ResponseBuilder = dependency(),
        request: Request = dependency(),
    ):
        logger.exception("Unhandled exception", exc_info=error)

        # Check if the error is a ServException subclass and use its status code
        status_code = (
            getattr(error, "status_code", 500)
            if isinstance(error, ServException)
            else 500
        )
        response.set_status(status_code)

        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")

            # Enhanced traceback for development mode
            if self._dev_mode:
                # Get full traceback with context
                tb_lines = traceback.format_exception(
                    type(error), error, error.__traceback__
                )
                full_traceback = "".join(tb_lines)

                # Also include exception chain if present
                if error.__cause__ or error.__context__:
                    full_traceback += "\n\n--- Exception Chain ---\n"
                    if error.__cause__:
                        cause_tb = traceback.format_exception(
                            type(error.__cause__),
                            error.__cause__,
                            error.__cause__.__traceback__,
                        )
                        full_traceback += f"Caused by: {''.join(cause_tb)}"
                    if error.__context__ and error.__context__ != error.__cause__:
                        context_tb = traceback.format_exception(
                            type(error.__context__),
                            error.__context__,
                            error.__context__.__traceback__,
                        )
                        full_traceback += f"During handling of: {''.join(context_tb)}"
            else:
                full_traceback = "".join(traceback.format_exception(error))

            context = {
                "status_code": status_code,
                "error_title": "Error",
                "error_message": "An unexpected error occurred.",
                "error_type": type(error).__name__,
                "error_str": str(error),
                "traceback": full_traceback,
                "request_path": request.path,
                "request_method": request.method,
                "show_details": self._dev_mode,
            }

            html_content = self._render_template("error/500.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": status_code,
                "error": type(error).__name__,
                "message": str(error)
                if self._dev_mode
                else "An unexpected error occurred.",
                "path": request.path,
                "method": request.method,
            }

            if self._dev_mode:
                # Enhanced traceback for JSON response in dev mode
                tb_lines = traceback.format_exception(
                    type(error), error, error.__traceback__
                )
                error_data["traceback"] = tb_lines

                # Include exception chain
                if error.__cause__:
                    cause_tb = traceback.format_exception(
                        type(error.__cause__),
                        error.__cause__,
                        error.__cause__.__traceback__,
                    )
                    error_data["caused_by"] = cause_tb
                if error.__context__ and error.__context__ != error.__cause__:
                    context_tb = traceback.format_exception(
                        type(error.__context__),
                        error.__context__,
                        error.__context__.__traceback__,
                    )
                    error_data["context"] = context_tb

            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            if self._dev_mode:
                # Full traceback in plaintext for dev mode
                tb_lines = traceback.format_exception(
                    type(error), error, error.__traceback__
                )
                full_traceback = "".join(tb_lines)
                error_message = f"{status_code} Error: {type(error).__name__}: {error}\n\nFull Traceback:\n{full_traceback}"
            else:
                error_message = f"{status_code} Error: An unexpected error occurred."
            response.body(error_message)

    @inject
    async def _default_404_handler(
        self,
        error: HTTPNotFoundException,
        response: ResponseBuilder = dependency(),
        request: Request = dependency(),
    ):
        response.set_status(HTTPNotFoundException.status_code)

        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")
            context = {
                "status_code": HTTPNotFoundException.status_code,
                "error_title": "Not Found",
                "error_message": error.args[0]
                if error.args
                else "The requested resource was not found.",
                "error_type": "NotFound",
                "request_path": request.path,
                "request_method": request.method,
                "show_details": False,
            }

            html_content = self._render_template("error/404.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": HTTPNotFoundException.status_code,
                "error": "NotFound",
                "message": "The requested resource was not found.",
                "path": request.path,
                "method": request.method,
            }
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            response.body(
                f"404 Not Found: The requested resource ({request.path}) was not found."
            )

    @inject
    async def _default_405_handler(
        self,
        error: HTTPMethodNotAllowedException,
        response: ResponseBuilder = dependency(),
        request: Request = dependency(),
    ):
        response.set_status(HTTPMethodNotAllowedException.status_code)

        allowed_methods_str = (
            ", ".join(error.allowed_methods) if error.allowed_methods else ""
        )
        if error.allowed_methods:
            response.add_header("Allow", allowed_methods_str)

        # Check if the client accepts HTML
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Use HTML response
            response.content_type("text/html")
            context = {
                "status_code": HTTPMethodNotAllowedException.status_code,
                "error_title": "Method Not Allowed",
                "error_message": error.args[0]
                if error.args
                else "The method used is not allowed for the requested resource.",
                "error_type": type(error).__name__,
                "error_str": str(error),
                "request_path": request.path,
                "request_method": request.method,
                "allowed_methods": allowed_methods_str,
                "show_details": False,
            }

            html_content = self._render_template("error/405.html", context)
            response.body(html_content)
        elif "application/json" in accept_header:
            # Use JSON response
            response.content_type("application/json")
            error_data = {
                "status_code": HTTPMethodNotAllowedException.status_code,
                "error": "MethodNotAllowed",
                "message": error.args[0]
                if error.args
                else "The method used is not allowed for the requested resource.",
                "path": request.path,
                "method": request.method,
                "allowed_methods": error.allowed_methods
                if error.allowed_methods
                else [],
            }
            response.body(json.dumps(error_data))
        else:
            # Use plaintext response
            response.content_type("text/plain")
            message = (
                error.args[0]
                if error.args
                else f"The method used is not allowed for the requested resource {request.path}."
            )
            response.body(f"405 Method Not Allowed: {message}")

    @inject
    async def _run_error_handler(
        self, error: Exception, container: Container = dependency()
    ):
        response_builder = container.get(ResponseBuilder)
        if not response_builder._headers_sent:
            response_builder.clear()

        handler_key = type(error)
        handler = self._error_handlers.get(handler_key)
        if not handler:
            for err_type, hnd in self._error_handlers.items():
                if isinstance(error, err_type):
                    handler = hnd
                    break
        handler = handler or self._default_error_handler

        try:
            await container.call(handler, error)
        except Exception as e:
            logger.exception(
                "Critical error in error handling mechanism itself", exc_info=True
            )
            if handler is not self._default_error_handler:
                e.__context__ = error
                ultimate_response_builder = container.get(ResponseBuilder)
                if not ultimate_response_builder._headers_sent:
                    ultimate_response_builder.clear()
                await container.call(self._default_error_handler, e)

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

            container.instances[Request] = request
            container.instances[ResponseBuilder] = response_builder
            container.instances[Container] = container
            container.instances[Router] = router_instance_for_request

            error_to_propagate = None
            try:
                # Pass the newly created router_instance to the event
                await self.emit("app.request.begin", container=container)

                # Run middleware stack
                try:
                    await self._run_middleware_stack(
                        container=container, request_instance=request
                    )
                except Exception as e:
                    error_to_propagate = e

                # Handle any errors that occurred
                if error_to_propagate:
                    await container.call(self._run_error_handler, error_to_propagate)

                await self.emit(
                    "app.request.end", error=error_to_propagate, container=container
                )

            except Exception as e:
                logger.exception(
                    "Unhandled exception during request processing", exc_info=e
                )
                await container.call(self._run_error_handler, e)
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

    async def _run_middleware_stack(
        self, container: Container, request_instance: Request
    ):
        stack = []
        error_to_propagate = None
        router_instance = container.get(Router)

        for middleware_factory in self._middleware:
            try:
                # For middleware functions, use container.call to properly inject dependencies
                # Don't await the result since it's an async generator
                middleware_iterator = container.call(middleware_factory)
                await anext(middleware_iterator)
            except Exception as e:
                logger.exception(
                    f"Error during setup of middleware {getattr(middleware_factory, '__name__', str(middleware_factory))}",
                    exc_info=True,
                )
                error_to_propagate = e
                break
            else:
                stack.append(middleware_iterator)

        if not error_to_propagate:
            await self.emit(
                "app.request.before_router",
                container=container,
                request=request_instance,
                router_instance=router_instance,
            )
            try:
                resolved_route_info = router_instance.resolve_route(
                    request_instance.path, request_instance.method
                )
                if not resolved_route_info:
                    raise HTTPNotFoundException(
                        f"No route found for {request_instance.method} {request_instance.path}"
                    )

            except Exception as e:
                logger.info(
                    f"Router resolution resulted in exception: {type(e).__name__}: {e}"
                )
                error_to_propagate = e

            else:
                handler_callable, path_params, route_settings = resolved_route_info

                # Create a branch of the container with route settings
                with container.branch() as route_container:
                    # Add route settings to the container using RouteSettings
                    from serv.routing import RouteSettings

                    route_container.instances[RouteSettings] = RouteSettings(
                        **route_settings
                    )

                    try:
                        await route_container.call(handler_callable, **path_params)
                    except Exception as e:
                        logger.info(
                            f"Handler execution resulted in exception: {type(e).__name__}: {e}"
                        )
                        error_to_propagate = e

            await self.emit(
                "app.request.after_router",
                container=container,
                request=request_instance,
                error=error_to_propagate,
                router_instance=router_instance,
            )

        for middleware_iterator in reversed(stack):
            try:
                if error_to_propagate:
                    await middleware_iterator.athrow(error_to_propagate)
                    error_to_propagate = None
                else:
                    await anext(middleware_iterator)
            except StopAsyncIteration:
                pass
            except Exception as e:
                logger.exception("Error during unwinding of middleware", exc_info=True)
                if error_to_propagate:
                    e.__context__ = error_to_propagate
                error_to_propagate = e

        if error_to_propagate:
            raise error_to_propagate

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send):
        """Handle WebSocket connections."""
        with self._container.branch() as container:
            router_instance_for_request = Router()
            container.instances[Container] = container
            container.instances[Router] = router_instance_for_request

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
                import inspect
                from typing import get_type_hints, get_args, get_origin
                from serv.websocket import WebSocket, FrameType

                frame_type = FrameType.TEXT  # Default frame type
                
                try:
                    # Get type hints for the handler
                    type_hints = get_type_hints(handler_callable, include_extras=True)
                    
                    # Look for WebSocket parameter with frame type annotation
                    for param_name, param_type in type_hints.items():
                        if get_origin(param_type) is not None:
                            # Check if it's Annotated[WebSocket, FrameType.X]
                            origin = get_origin(param_type)
                            if origin is type(type_hints.get("__annotated__", type(None))):  # Annotated type
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
                    from serv.routing import RouteSettings
                    
                    route_container.instances[RouteSettings] = RouteSettings(**route_settings)
                    route_container.instances[WebSocket] = websocket

                    try:
                        # Call the WebSocket handler
                        await route_container.call(handler_callable, **path_params)
                    except Exception as e:
                        logger.exception(f"WebSocket handler error: {e}")
                        # Close connection with error code
                        if websocket.is_connected:
                            await websocket.close(code=1011, reason="Internal server error")

                await container.call(self._emit.emit, "app.websocket.end")

            except Exception as e:
                logger.exception(f"Unhandled exception during WebSocket processing: {e}")
                # Attempt to close connection gracefully
                try:
                    await send({"type": "websocket.close", "code": 1011})
                except Exception:
                    pass  # Connection may already be closed
                
                await container.call(self._emit.emit, "app.websocket.end", error=e)
