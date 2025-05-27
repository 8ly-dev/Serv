"""Defines a base type that can observe events happening in the Serv app. Handlers are defined as methods on the class
with names following the format '[optional_]on_{event_name}'. This gives the author the ability to make readable
function names like 'set_role_on_user_create' or 'create_annotations_on_form_submit'."""

import re
import sys
from collections import defaultdict
from inspect import isawaitable
from pathlib import Path
from typing import Any

from bevy import get_container
from bevy.containers import Container

import serv.extensions.loader as pl

type ListenerMapping = dict[str, list[str]]


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

            event = re.match(r"^(?:.+_)?on_(.*)$", name)
            if not event:
                continue

            callback = getattr(cls, name)
            if not callable(callback):
                continue

            event_name = event.group(1)
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

        # Support both extension_spec and extension_spec for backward compatibility
        spec = extension_spec or extension_spec

        if spec:
            self.__extension_spec__ = spec
            self.__extension_spec__ = spec  # Backward compatibility
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
            self.__extension_spec__ = spec  # Backward compatibility
        else:
            # Stand-alone mode - no extension spec required
            self.__extension_spec__ = None
            self.__extension_spec__ = None  # Backward compatibility

    async def on(
        self,
        event_name: str,
        container: Container | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Receives event notifications.

        This method will be called by the application when an event this listener
        is registered for occurs. Subclasses should implement this method to handle
        specific events.

        Args:
            event_name: The name of the event that occurred.
            **kwargs: Arbitrary keyword arguments associated with the event.
        """
        event_name = re.sub(r"[^a-z0-9]+", "_", event_name.lower())
        for listener_handler_name in self.__listeners__[event_name]:
            callback = getattr(self, listener_handler_name)
            result = get_container(container).call(callback, *args, **kwargs)
            if isawaitable(result):
                await result


# Backward compatibility alias
Extension = Listener
