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

    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route(self.path, self._handler_wrapper, methods=self.methods)

    async def _handler_wrapper(self, request: Request = dependency(), container: Container = dependency(), **path_params):
        self.was_called = True
        self.received_kwargs = {**path_params, "request": request, "container": container} # For inspection

        # Call the original handler (e.g., hello_handler from the test)
        # using the per-request container. Path parameters are passed explicitly.
        # Other dependencies (like Request, ResponseBuilder) should be declared
        # in self.handler's signature with ` = dependency()` if needed.
        await container.call(self.handler, **path_params)

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