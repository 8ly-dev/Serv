import json
import logging
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from bevy import Inject, injectable
from bevy.containers import Container
from jinja2 import Environment, FileSystemLoader

from serv._routing import HTTPNotFoundException, Router, RouteSettings
from serv.exceptions import HTTPMethodNotAllowedException, ServException
from serv.requests import Request
from serv.responses import ResponseBuilder

logger = logging.getLogger(__name__)


class MiddlewareManager:
    """Manages middleware stack and error handling for the Serv web framework.

    The MiddlewareManager encapsulates all middleware execution logic and error handling
    functionality, providing a clean separation of concerns from the main App class.
    It handles middleware registration, execution, error handler registration, and
    template rendering for error responses.

    The middleware system supports async generator functions that can:
    - Modify requests before they reach route handlers
    - Modify responses after route handlers execute
    - Implement cross-cutting concerns like authentication, logging, CORS
    - Handle errors during request processing

    Error handling provides:
    - Custom error handlers for specific exception types
    - Default error handlers for common HTTP errors (404, 405, 500)
    - Content negotiation for error responses (HTML, JSON, plain text)
    - Development vs production error display modes
    - Template rendering with fallback error pages

    Examples:
        Basic middleware manager setup:

        ```python
        middleware_manager = MiddlewareManager(dev_mode=True)

        # Add logging middleware
        @injectable
        async def logging_middleware(request: Inject[Request]):
            print(f"Processing {request.method} {request.path}")
            yield  # Pass control to next middleware/handler
            print(f"Finished processing {request.path}")

        middleware_manager.add_middleware(logging_middleware)
        ```

        Custom error handler registration:

        ```python
        @injectable
        async def custom_404_handler(
            error: HTTPNotFoundException,
            response: Inject[ResponseBuilder]
        ):
            response.set_status(404)
            response.content_type("text/html")
            response.body("<h1>Custom 404 Page</h1>")

        middleware_manager.add_error_handler(HTTPNotFoundException, custom_404_handler)
        ```

        Running the middleware stack:

        ```python
        # Within request handling
        try:
            await middleware_manager.run_middleware_stack(
                container=container,
                request_instance=request,
                emit_callback=app.emit
            )
        except Exception as e:
            await middleware_manager.run_error_handler(e, container=container)
        ```

    Args:
        dev_mode: Enable development mode with enhanced error reporting and debugging.
            When True, provides detailed tracebacks and error context. Should be False
            in production environments.
    """

    def __init__(self, dev_mode: bool = False):
        """Initialize the middleware manager.

        Args:
            dev_mode: Enable development mode features including enhanced error
                reporting, detailed tracebacks, and development-specific behaviors.
                Should be False in production.
        """
        self._dev_mode = dev_mode
        self._middleware: list[Callable[[], AsyncIterator[None]]] = []
        self._error_handlers: dict[
            type[Exception], Callable[[Exception], Awaitable[None]]
        ] = {}

        # Register default error handlers
        self._register_default_error_handlers()

    def _register_default_error_handlers(self):
        """Register default error handlers for common HTTP errors."""
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

            middleware_manager.add_middleware(logging_middleware)
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

            middleware_manager.add_middleware(auth_middleware)
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

            middleware_manager.add_middleware(cors_middleware)
            ```

        Note:
            Middleware is executed in LIFO (Last In, First Out) order during request
            processing, and FIFO (First In, First Out) order during response processing.
        """
        self._middleware.append(middleware)

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

            middleware_manager.add_error_handler(HTTPNotFoundException, custom_404_handler)
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

            middleware_manager.add_error_handler(ValidationError, validation_error_handler)
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

            middleware_manager.add_error_handler(Exception, generic_error_handler)
            ```
        """
        self._error_handlers[error_type] = handler

    def _get_template_locations(self) -> list[Path]:
        """Get the template locations for error template rendering.

        Returns a list of paths to search for templates, prioritizing
        project-specific templates over framework defaults.

        Returns:
            List of Path objects representing template search directories.
        """
        return [Path.cwd() / "templates", Path(__file__).parent.parent / "templates"]

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context.

        Uses Jinja2 template engine to render error pages and other templates.
        If template loading fails, provides fallback HTML content for error pages.

        Args:
            template_name: Name of the template to render (e.g., "error/404.html")
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered template as HTML string

        Raises:
            Exception: If template loading/rendering fails and no fallback is available

        Examples:
            Render a 404 error template:

            ```python
            context = {
                "status_code": 404,
                "error_title": "Not Found",
                "error_message": "The requested page was not found.",
                "request_path": "/missing-page",
                "request_method": "GET"
            }
            html = middleware_manager._render_template("error/404.html", context)
            ```
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

    @injectable
    async def _default_error_handler(
        self,
        error: Exception,
        response: Inject[ResponseBuilder],
        request: Inject[Request],
    ):
        """Default handler for unhandled exceptions.

        Provides comprehensive error handling with content negotiation,
        development vs production modes, and detailed error information.
        Supports HTML, JSON, and plain text error responses.

        Args:
            error: The exception that occurred
            response: Response builder for setting status and content
            request: Request object for accessing headers and request info
        """
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

    @injectable
    async def _default_404_handler(
        self,
        error: HTTPNotFoundException,
        response: Inject[ResponseBuilder],
        request: Inject[Request],
    ):
        """Default handler for 404 Not Found errors.

        Provides content-negotiated responses for missing resources,
        supporting HTML, JSON, and plain text formats.

        Args:
            error: The HTTPNotFoundException that occurred
            response: Response builder for setting status and content
            request: Request object for accessing headers and request info
        """
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

    @injectable
    async def _default_405_handler(
        self,
        error: HTTPMethodNotAllowedException,
        response: Inject[ResponseBuilder],
        request: Inject[Request],
    ):
        """Default handler for 405 Method Not Allowed errors.

        Provides content-negotiated responses for unsupported HTTP methods,
        including proper Allow header with supported methods.

        Args:
            error: The HTTPMethodNotAllowedException that occurred
            response: Response builder for setting status and content
            request: Request object for accessing headers and request info
        """
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

    @injectable
    async def run_error_handler(self, error: Exception, container: Inject[Container]):
        """Execute the appropriate error handler for the given exception.

        Finds and executes the most specific error handler registered for the
        exception type. Falls back to the default error handler if no specific
        handler is found. Provides error recovery if the error handler itself fails.

        Args:
            error: The exception to handle
            container: Dependency injection container for handler execution

        Examples:
            Handle an error during request processing:

            ```python
            try:
                # Some request processing code
                raise ValueError("Something went wrong")
            except Exception as e:
                await middleware_manager.run_error_handler(e, container=container)
            ```

        Note:
            If a custom error handler fails, the system will fall back to the
            default error handler to ensure a response is always sent.
        """
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

    async def run_middleware_stack(
        self,
        container: Container,
        request_instance: Request,
        emit_callback: Callable[..., Awaitable[None]],
    ):
        """Execute the complete middleware stack and route handling.

        Runs all registered middleware in order, executes the route handler,
        and then unwinds the middleware stack in reverse order. Handles errors
        at each stage and provides proper cleanup.

        Args:
            container: Dependency injection container for middleware execution
            request_instance: The current HTTP request being processed
            emit_callback: Function to emit application events during processing

        Raises:
            Exception: Any unhandled exception from middleware or route handler

        Examples:
            Execute middleware stack during request processing:

            ```python
            # Within the main request handler
            try:
                await middleware_manager.run_middleware_stack(
                    container=container,
                    request_instance=request,
                    emit_callback=app.emit
                )
            except Exception as e:
                await middleware_manager.run_error_handler(e, container=container)
            ```

        Note:
            Middleware is executed in LIFO order during setup and FIFO order
            during teardown, creating a "sandwich" effect around route handling.
        """
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
            await emit_callback(
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
                    route_container.add(RouteSettings, RouteSettings(**route_settings))

                    # Ensure essential dependencies are available in route container
                    # Copy from parent container if missing
                    for dep_type in [Request, ResponseBuilder, Container, Router]:
                        try:
                            parent_instance = container.get(dep_type)
                            # Try to get from route container to see if it's already there
                            try:
                                route_container.get(dep_type)
                            except Exception:
                                # Not found in route container, add it
                                route_container.add(dep_type, parent_instance)
                        except Exception:
                            # Parent doesn't have it, skip
                            pass

                    try:
                        await route_container.call(handler_callable, **path_params)
                    except Exception as e:
                        logger.info(
                            f"Handler execution resulted in exception: {type(e).__name__}: {e}"
                        )
                        error_to_propagate = e

            await emit_callback(
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
