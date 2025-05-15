from typing import Any, Awaitable, Callable
from bevy import dependency
from bevy.containers import Container

from serv.observers import Observer
from serv.routing import Router, get_current_router
from serv.requests import Request
from serv.responses import ResponseBuilder


class RouteAddingPlugin(Observer):
    def __init__(self, path: str, handler: Callable[..., Awaitable[None]], methods: list[str] | None = None):
        self.path = path
        self.handler = handler
        self.methods = methods
        self.was_called = False
        self.received_kwargs = None

    async def on(self, event_name: str, **kwargs: Any) -> None:
        if event_name == "app.request.begin": # Add route early in the request lifecycle
            container = kwargs.get("container")
            if container:
                router = get_current_router(container) # Use the helper
                router.add_route(self.path, self._handler_wrapper, methods=self.methods)

    async def _handler_wrapper(self, *args, **kwargs_handler):
        self.was_called = True
        self.received_kwargs = kwargs_handler
        # Call the actual handler provided to the plugin
        # This assumes the handler can be called by Bevy using the current container
        container = get_current_router()._container # Bit of a hack to get current container, assumes Router has it or can access it.
        # Better: if handler needs DI, it should be set up when adding route.
        # For simplicity now, direct call or let Bevy handle if it's registered.
        # If the handler itself is a method of a Bevy-managed object, container.call would be best.
        # For a simple callable from test: await self.handler(*args, **kwargs_handler)
        current_container = kwargs_handler.get("container", None) # Assuming handler might get container
        if not current_container:
             # Try to get it from a known injectable if possible (e.g. Request)
             req = kwargs_handler.get("request")
             if req:
                 current_container = req.scope.get("container") # If app stores container in scope
        
        if current_container:
            await current_container.call(self.handler, *args, **kwargs_handler)
        else:
            # Fallback if container cannot be easily determined for handler call
            # This might fail if handler has unmet Bevy dependencies.
            await self.handler(*args, **kwargs_handler)

class EventWatcherPlugin(Observer):
    def __init__(self):
        self.events_seen = []

    async def on(self, event_name: str, **kwargs: Any) -> None:
        self.events_seen.append((event_name, kwargs))

# Example of a simple middleware for testing
# Middleware are defined as async generator factories
async def example_header_middleware(request: Request = dependency(), response: ResponseBuilder = dependency()) -> None:
    # Code here runs before the next middleware/handler
    response.add_header("X-Test-Middleware-Before", "active")
    yield
    # Code here runs after the next middleware/handler
    response.add_header("X-Test-Middleware-After", "active") 