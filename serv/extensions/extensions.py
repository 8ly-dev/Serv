"""Defines a base type that can observe events happening in the Serv app. Handlers are defined as methods on the class
with names following the format '[optional_]on_{event_name}'. This gives the author the ability to make readable
function names like 'set_role_on_user_create' or 'create_annotations_on_form_submit'."""

import sys
from collections import defaultdict
from functools import wraps
from inspect import get_annotations, isawaitable, signature
from pathlib import Path
from typing import Any

from bevy import dependency, get_container, inject
from bevy.containers import Container

import serv.app as app
import serv.extensions.loader as pl

type ListenerMapping = dict[str, list[str]]


class Context:
    """Event context object that acts like a dictionary with additional event metadata.

    The Context object provides access to all keyword arguments passed to an event
    emission, while also including the event name for reference.

    Examples:
        Accessing event data:

        ```python
        class MyListener(Listener):
            @on("user.created")
            async def handle_user_created(self, context: Context):
                user_id = context["user_id"]
                email = context["email"]
                print(f"Event: {context.event_name}, User: {user_id}")
        ```

        Using both context and direct parameters:

        ```python
        class MyListener(Listener):
            @on("user.created")
            async def handle_user_created(self, user_id: int, context: Context):
                # user_id is injected directly
                # context provides access to all parameters and event name
                print(f"Event: {context.event_name}, User: {user_id}")
                if "email" in context:
                    print(f"Email: {context['email']}")
        ```
    """

    def __init__(self, event_name: str, **kwargs):
        self.event_name = event_name
        self._data = kwargs

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __repr__(self) -> str:
        return f"Context(event_name={self.event_name!r}, data={self._data!r})"


class _OnDecorator:
    """Decorator class for marking listener methods with event names."""

    def __init__(self, events: set[str]):
        self.events = events

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Store the events this handler supports
        wrapper.__event_names__ = self.events
        return wrapper

    def __or__(self, other):
        """Support for @on("event1") | on("event2") syntax"""
        if isinstance(other, _OnDecorator):
            return _OnDecorator(self.events | other.events)
        return NotImplemented


def on(event_name: str) -> _OnDecorator:
    """Decorator for marking event handler methods.

    This decorator replaces the naming-based event detection with explicit
    event name specification.

    Args:
        event_name: The name of the event to listen for (e.g., "app.request.begin")

    Examples:
        Basic event handler:

        ```python
        class MyListener(Listener):
            @on("app.request.begin")
            async def setup_request(self, router: Router = dependency()):
                # Handle app request begin event
                pass
        ```

        Handler for multiple events:

        ```python
        class MyListener(Listener):
            @on("user.created") | on("user.updated")
            async def handle_user_changes(self, user_id: int):
                # Handle both user created and updated events
                pass
        ```

        Handler with context:

        ```python
        class MyListener(Listener):
            @on("order.processed")
            async def handle_order(self, context: Context):
                order_id = context["order_id"]
                print(f"Processing order {order_id} for event {context.event_name}")
        ```
    """
    return _OnDecorator({event_name})


def search_for_extension_directory(path: Path) -> Path | None:
    while path.name:
        if (path / "extension.yaml").exists() or (path / "extension.yaml").exists():
            return path

        path = path.parent

    raise Exception("Extension directory not found")


class Listener:
    """Base class for creating Serv event listeners.

    Listeners extend the functionality of Serv applications by responding to events
    that occur during the application lifecycle. They can handle application events,
    modify requests/responses, and integrate with external services.

    Listener classes automatically register event handlers based on method names
    following the pattern `on_{event_name}` or `{prefix}_on_{event_name}`. This
    allows for readable method names and automatic event subscription.

    Common Events:
    - `app_startup`: Application is starting up
    - `app_shutdown`: Application is shutting down
    - `app_request_begin`: New request is being processed
    - `app_request_end`: Request processing is complete
    - `extension_loaded`: Extension has been loaded
    - Custom events emitted by your application

    Examples:
        Basic listener with event handlers:

        ```python
        from serv.extensions import Listener
        from serv.routing import Router
        from bevy import dependency

        class MyListener(Listener):
            async def on_app_startup(self):
                print("Application is starting!")

            async def on_app_request_begin(self, router: Router = dependency()):
                # Add routes when app starts handling requests
                router.add_route("/hello", self.hello_handler, ["GET"])

            async def hello_handler(self, response: ResponseBuilder = dependency()):
                response.body("Hello from my listener!")

            async def on_app_shutdown(self):
                print("Application is shutting down!")
        ```

        Listener with custom event handlers:

        ```python
        class UserListener(Listener):
            async def on_user_created(self, user_id: int):
                print(f"User {user_id} was created!")

            async def send_email_on_user_created(self, user_id: int, email: str):
                # Send welcome email
                await self.send_welcome_email(email)

            async def on_user_deleted(self, user_id: int):
                # Cleanup user data
                await self.cleanup_user_data(user_id)
        ```

        Listener with dependency injection:

        ```python
        from serv.requests import Request
        from serv.responses import ResponseBuilder

        class AuthListener(Listener):
            async def on_app_request_begin(
                self,
                request: Request = dependency(),
                response: ResponseBuilder = dependency()
            ):
                # Check authentication for protected routes
                if request.path.startswith("/admin/"):
                    auth_header = request.headers.get("authorization")
                    if not auth_header:
                        response.set_status(401)
                        response.body("Authentication required")
                        return
        ```

        Listener configuration:

        ```python
        class DatabaseListener(Listener):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                # Access extension configuration from extension.yaml
                config = self.__extension_spec__.config
                self.db_url = config.get("database_url", "sqlite:///app.db")
                self.pool_size = config.get("pool_size", 10)

            async def on_app_startup(self):
                # Initialize database connection
                self.db_pool = await create_db_pool(self.db_url, self.pool_size)
        ```

    Note:
        Listener methods that handle events can use dependency injection to access
        request/response objects, the router, and other services. The extension system
        automatically manages the lifecycle and ensures proper cleanup.
    """

    def __init_subclass__(cls, **kwargs) -> None:
        cls.__listeners__ = defaultdict(list)

        for name in dir(cls):
            if name.startswith("_"):
                continue

            callback = getattr(cls, name)
            if not callable(callback):
                continue

            if hasattr(callback, "__event_names__"):
                for event_name in callback.__event_names__:
                    cls.__listeners__[event_name].append(name)

    def __init__(
        self,
        *,
        extension_spec: "pl.ExtensionSpec | None" = None,
        stand_alone: bool = False,
    ):
        """Initialize the listener.

        Loads extension configuration and sets up any defined routers and routes
        if they are configured in the extension.yaml file.

        Args:
            extension_spec: Extension specification (preferred)
            extension_spec: Extension specification (backward compatibility)
            stand_alone: If True, don't attempt to load extension.yaml
        """
        self._stand_alone = stand_alone

        spec = None
        if extension_spec:
            spec = extension_spec

        elif not stand_alone:
            module = sys.modules[self.__module__]
            if not hasattr(module, "__extension_spec__") and not hasattr(
                module, "__extension_spec__"
            ):
                raise Exception(
                    f"Listener {self.__class__.__name__} does not exist in an extension package. No extension.yaml found in "
                    f"parent directories."
                )
            # Try extension_spec first, then extension_spec for backward compatibility
            spec = getattr(module, "__extension_spec__", None) or getattr(
                module, "__extension_spec__", None
            )

        self.__extension_spec__ = spec

    async def on(
        self,
        event_name: str,
        container: Container | None = None,
        **kwargs: Any,
    ) -> None:
        """Receives event notifications.

        This method will be called by the application when an event occurs that this
        listener is registered for. Handlers are called with keyword arguments only,
        and Context objects are injected for parameters with Context type annotation.

        Args:
            event_name: The name of the event that occurred.
            **kwargs: Arbitrary keyword arguments associated with the event.
        """
        # Find handlers for this exact event name
        if event_name not in self.__listeners__:
            return  # No handlers for this event

        for listener_handler_name in self.__listeners__[event_name]:
            callback = getattr(self, listener_handler_name)

            # Prepare arguments for the handler
            handler_kwargs = await self._prepare_handler_arguments(
                callback, event_name, kwargs, container
            )

            result = get_container(container).call(callback, **handler_kwargs)
            if isawaitable(result):
                await result

    @inject
    @staticmethod
    async def emit(
        event_name: str, _emitter: "app.EventEmitter" = dependency(), **kwargs: Any
    ):
        await _emitter.emit(event_name, **kwargs)

    async def _prepare_handler_arguments(
        self,
        callback: callable,
        event_name: str,
        event_kwargs: dict[str, Any],
        container: Container | None,
    ) -> dict[str, Any]:
        """Prepare arguments for a handler based on its signature."""
        try:
            sig = signature(callback)
            annotations = get_annotations(callback)
        except Exception:
            # If we can't get signature info, pass through all kwargs
            return event_kwargs

        handler_kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_annotation = annotations.get(param_name, param.annotation)

            # Check if parameter expects a Context object
            if param_annotation is Context or (
                hasattr(param_annotation, "__name__")
                and param_annotation.__name__ == "Context"
            ):
                handler_kwargs[param_name] = Context(event_name, **event_kwargs)
            elif param_name in event_kwargs:
                # Only pass parameters that match available event data
                handler_kwargs[param_name] = event_kwargs[param_name]
            # If parameter is not available and has no default, it will be handled by bevy

        return handler_kwargs


# Alias for Extension (same as Listener but clearer name for some use cases)
Extension = Listener
