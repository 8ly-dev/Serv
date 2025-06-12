"""Lifecycle management system for Serv applications.

This module provides the LifecycleManager class and EventEmitter that handle
ASGI lifecycle events, request/response processing, WebSocket connections,
and event emission for extension communication.

The LifecycleManager coordinates the entire request lifecycle from initial
ASGI entry point through middleware processing, routing, and final response
delivery.
"""

import asyncio
import logging
from asyncio import Task, get_running_loop
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
from bevy import Inject, injectable
from bevy.containers import Container

from serv._routing import Router
from serv.app.extensions import ExtensionManager
from serv.app.middleware import MiddlewareManager
from serv.database import DatabaseManager
from serv.extensions import Listener
from serv.protocols import EventEmitterProtocol, RouterProtocol
from serv.requests import Request
from serv.responses import ResponseBuilder

logger = logging.getLogger(__name__)


class EventEmitter(EventEmitterProtocol):
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

    def __init__(self, extension_manager: ExtensionManager):
        self._extension_manager = extension_manager

    @property
    def extensions(self) -> dict[Path, list[Listener]]:
        return self._extension_manager.extensions

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


class LifecycleManager:
    """Manages ASGI lifecycle, request processing, and event coordination.

    The LifecycleManager serves as the central coordinator for the entire
    application lifecycle, from ASGI entry point through request processing,
    middleware execution, routing, and response delivery.

    This class handles:
    - ASGI lifespan events (startup/shutdown)
    - HTTP request processing pipeline
    - WebSocket connection management
    - Event emission coordination
    - Database lifecycle management

    Examples:
        Basic lifecycle management:

        ```python
        from serv.app.lifecycle import LifecycleManager
        from serv.app.extensions import ExtensionManager
        from serv.app.middleware import MiddlewareManager

        # Initialize managers
        extension_manager = ExtensionManager()
        middleware_manager = MiddlewareManager()
        database_manager = DatabaseManager(config, container)

        # Create lifecycle manager
        lifecycle = LifecycleManager(
            extension_manager=extension_manager,
            middleware_manager=middleware_manager,
            database_manager=database_manager,
            container=container
        )

        # Use as ASGI callable
        await lifecycle(scope, receive, send)
        ```

        Event emission:

        ```python
        # Emit events during request processing
        await lifecycle.emit("user_login", user_id=123, container=container)

        # Synchronous emission (returns task)
        task = lifecycle.emit_sync("background_job", data=payload, container=container)
        ```

    Attributes:
        extension_manager: Manager for extension registration and coordination.
        middleware_manager: Manager for middleware stack execution.
        database_manager: Manager for database connections and lifecycle.
        container: Root dependency injection container.
    """

    def __init__(
        self,
        *,
        extension_manager: ExtensionManager,
        middleware_manager: MiddlewareManager,
        database_manager: DatabaseManager,
        container: Container,
        async_exit_stack=None,
    ):
        """Initialize the LifecycleManager.

        Args:
            extension_manager: Manager for extensions and listeners.
            middleware_manager: Manager for middleware stack execution.
            database_manager: Manager for database connections.
            container: Root dependency injection container.
            async_exit_stack: Optional async exit stack for cleanup coordination.
        """
        self._extension_manager = extension_manager
        self._middleware_manager = middleware_manager
        self._database_manager = database_manager
        self._container = container
        self._async_exit_stack = async_exit_stack

        # Initialize event emitter
        self._emit = EventEmitter(extension_manager)

    @property
    def event_emitter(self) -> EventEmitter:
        """Get the event emitter instance."""
        return self._emit

    @injectable
    def emit_sync(self, event: str, *, container: Inject[Container], **kwargs) -> Task:
        """Emit an event synchronously, returning a task.

        This method creates a background task for event emission, allowing
        the calling code to continue execution without waiting for all
        listeners to complete.

        Args:
            event: Name of the event to emit.
            container: Dependency injection container for listener execution.
            **kwargs: Event data to pass to listeners.

        Returns:
            Task object representing the event emission process.

        Examples:
            Emit background events:

            ```python
            # Fire and forget event emission
            task = lifecycle.emit_sync("analytics_event", user_action="click", container=container)

            # Optional: await the task later if needed
            await task
            ```
        """
        return self._emit.emit_sync(event, container=container, **kwargs)

    @injectable
    async def emit(self, event: str, *, container: Inject[Container], **kwargs) -> None:
        """Emit an event asynchronously, waiting for all listeners.

        This method broadcasts an event to all registered listeners and waits
        for all of them to complete processing before returning.

        Args:
            event: Name of the event to emit.
            container: Dependency injection container for listener execution.
            **kwargs: Event data to pass to listeners.

        Examples:
            Emit critical events:

            ```python
            # Wait for all listeners to complete
            await lifecycle.emit("app.startup", container=container)
            await lifecycle.emit("user_created", user_id=123, email="user@example.com", container=container)
            ```
        """
        await self._emit.emit(event, container=container, **kwargs)

    async def handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        """Handle ASGI lifespan events (startup/shutdown).

        This method processes lifespan events from the ASGI server, coordinating
        application startup and shutdown sequences including database initialization,
        extension notification, and cleanup operations.

        Args:
            scope: ASGI scope containing lifespan information.
            receive: ASGI receive callable for receiving events.
            send: ASGI send callable for sending responses.

        Examples:
            ASGI lifespan handling:

            ```python
            # This is called automatically by the ASGI server
            # during application startup and shutdown
            await lifecycle.handle_lifespan(scope, receive, send)
            ```

        Note:
            This method handles both startup and shutdown events:
            - Startup: Initializes databases, emits app.startup event
            - Shutdown: Emits app.shutdown event, shuts down databases, runs cleanup
        """
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
                    if self._async_exit_stack:
                        await self._async_exit_stack.aclose()

    async def _lifespan_iterator(self, receive: Receive):
        """Iterate over ASGI lifespan events until shutdown.

        Args:
            receive: ASGI receive callable for receiving events.

        Yields:
            ASGI lifespan event dictionaries.
        """
        event = {}
        while event.get("type") != "lifespan.shutdown":
            event = await receive()
            yield event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI application entry point.

        This method serves as the main ASGI callable, routing incoming requests
        to the appropriate handlers based on scope type (HTTP, WebSocket, lifespan).

        Args:
            scope: ASGI scope containing request information.
            receive: ASGI receive callable for receiving data.
            send: ASGI send callable for sending responses.

        Examples:
            ASGI server integration:

            ```python
            # For uvicorn, gunicorn, etc.
            app = LifecycleManager(...)

            # The server calls this method for each request
            await app(scope, receive, send)
            ```

        Note:
            This method dispatches to:
            - handle_lifespan() for lifespan events
            - _handle_request() for HTTP requests
            - _handle_websocket() for WebSocket connections
        """
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
        """Handle HTTP requests through the complete processing pipeline.

        This method coordinates the entire HTTP request lifecycle including:
        - Request object creation and dependency injection setup
        - Extension notification (app.request.begin)
        - Middleware stack execution
        - Error handling and recovery
        - Extension notification (app.request.end)
        - Final response delivery

        Args:
            scope: ASGI HTTP scope containing request information.
            receive: ASGI receive callable for receiving request data.
            send: ASGI send callable for sending response data.

        Examples:
            Request processing flow:

            ```python
            # This method is called automatically for HTTP requests
            # It coordinates the entire request/response cycle
            await lifecycle._handle_request(scope, receive, send)
            ```

        Note:
            The method uses container branching to create isolated dependency
            injection contexts for each request, ensuring thread safety and
            proper resource cleanup.
        """
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
        """Handle WebSocket connections and route to appropriate handlers.

        This method manages WebSocket connection lifecycle including:
        - Connection establishment and routing
        - Frame type detection from handler annotations
        - WebSocket instance creation and dependency injection
        - Handler execution with proper error handling
        - Connection cleanup and event notification

        Args:
            scope: ASGI WebSocket scope containing connection information.
            receive: ASGI receive callable for receiving WebSocket frames.
            send: ASGI send callable for sending WebSocket frames.

        Examples:
            WebSocket handling:

            ```python
            # This method is called automatically for WebSocket connections
            # It handles the complete WebSocket lifecycle
            await lifecycle._handle_websocket(scope, receive, send)
            ```

        Note:
            The method automatically detects frame types (TEXT/BINARY) from
            handler annotations and creates appropriate WebSocket instances
            for dependency injection.
        """
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