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

import serv.plugins.loader as pl

type ListenerMapping = dict[str, list[str]]


def search_for_plugin_directory(path: Path) -> Path | None:
    while path.name:
        if (path / "plugin.yaml").exists():
            return path

        path = path.parent

    raise Exception("Plugin directory not found")


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
    - `plugin_loaded`: Plugin has been loaded
    - Custom events emitted by your application

    Examples:
        Basic listener with event handlers:

        ```python
        from serv.plugins import Listener
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
                # Access plugin configuration from plugin.yaml
                config = self.__plugin_spec__.config
                self.db_url = config.get("database_url", "sqlite:///app.db")
                self.pool_size = config.get("pool_size", 10)

            async def on_app_startup(self):
                # Initialize database connection
                self.db_pool = await create_db_pool(self.db_url, self.pool_size)
        ```

    Note:
        Listener methods that handle events can use dependency injection to access
        request/response objects, the router, and other services. The plugin system
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
        self, *, plugin_spec: "pl.PluginSpec | None" = None, stand_alone: bool = False
    ):
        """Initialize the listener.

        Loads plugin configuration and sets up any defined routers and routes
        if they are configured in the plugin.yaml file.

        Args:
            stand_alone: If True, don't attempt to load plugin.yaml
        """
        self._stand_alone = stand_alone
        if plugin_spec:
            self.__plugin_spec__ = plugin_spec
        elif not stand_alone:
            module = sys.modules[self.__module__]
            if not hasattr(module, "__plugin_spec__"):
                raise Exception(
                    f"Listener {self.__class__.__name__} does not exist in a plugin package. No plugin.yaml found in "
                    f"parent directories."
                )
            self.__plugin_spec__ = module.__plugin_spec__
        else:
            # Stand-alone mode - no plugin spec required
            self.__plugin_spec__ = None

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
Plugin = Listener
