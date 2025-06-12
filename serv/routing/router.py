from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, dataclass_transform, overload

from bevy import Inject, injectable
from bevy.containers import Container

from serv.protocols import RouterProtocol

if TYPE_CHECKING:
    import serv.routes as routes


@dataclass_transform()
class RouteSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Router(RouterProtocol):
    """HTTP request router for mapping URLs to handlers.

    The Router class is responsible for matching incoming HTTP requests to the
    appropriate handler functions or Route classes. It supports path parameters,
    HTTP method filtering, route mounting, and URL generation.

    Features:
    - Path parameter extraction (e.g., `/users/{id}`)
    - HTTP method-specific routing
    - Route mounting and sub-routers
    - URL generation with `url_for()`
    - Route settings and metadata
    - Flexible handler types (functions, Route classes)
    - WebSocket route support

    Examples:
        Basic router setup:

        ```python
        from serv.routing.router import Router

        router = Router()

        # Add function-based routes
        async def get_users():
            return {"users": []}

        router.add_route("/users", get_users, ["GET"])

        # Add Route class
        class UserRoute:
            async def handle_get(self, request):
                return {"user": "data"}

        router.add_route("/users/{id}", UserRoute)

        # Add WebSocket handler
        async def websocket_handler(websocket):
            async for message in websocket:
                await websocket.send(message)

        router.add_websocket("/ws", websocket_handler)
        ```

        Router with settings:

        ```python
        router = Router(settings={
            "auth_required": True,
            "rate_limit": 100
        })
        ```

        Mounting sub-routers:

        ```python
        api_router = Router()
        api_router.add_route("/users", users_handler)
        api_router.add_route("/posts", posts_handler)

        main_router = Router()
        main_router.mount("/api/v1", api_router)
        # Now /api/v1/users and /api/v1/posts are available
        ```

    Args:
        settings: Optional dictionary of router-level settings that will be
            available to all routes handled by this router.
    """

    def __init__(self, settings: dict[str, Any] = None):
        # Stores tuples of (path_pattern, methods, handler_callable, settings)
        self._routes: list[
            tuple[str, frozenset[str] | None, Callable, dict[str, Any]]
        ] = []
        # Stores WebSocket routes as tuples of (path_pattern, handler_callable, settings)
        self._websocket_routes: list[tuple[str, Callable, dict[str, Any]]] = []
        # Stores mapping of (route_class -> path_pattern) for url_for lookups
        self._route_class_paths: dict[type[routes.Route], list[str]] = {}
        # Stores mapping of route path patterns to settings
        self._route_settings: dict[str, dict[str, Any]] = {}
        # Stores tuples of (mount_path, router_instance)
        self._mounted_routers: list[tuple[str, Router]] = []
        self._sub_routers: list[Router] = []
        # Router-level settings
        self._settings: dict[str, Any] = settings or {}

    @overload
    def add_route(
        self,
        path: str,
        handler: "type[routes.Route]",
        *,
        settings: dict[str, Any] = None,
    ): ...

    @overload
    def add_route(
        self,
        path: str,
        handler: "Callable[..., Awaitable[Any]]",
        methods: Sequence[str] | None = None,
        *,
        settings: dict[str, Any] = None,
    ): ...

    def add_route(
        self,
        path: str,
        handler: "Callable[..., Awaitable[Any]] | type[routes.Route]",
        methods: Sequence[str] | None = None,
        *,
        settings: dict[str, Any] = None,
        container: Container = None,
    ):
        """Adds a route to this router.

        This method can handle both direct route handlers and Route objects. For Route objects,
        it will automatically register all method and form handlers defined in the route.

        Args:
            path: The path pattern for the route.
            handler: Either a Route object or an async handler function.
            methods: A list of HTTP methods (e.g., ['GET', 'POST']). Only used when handler is a function.
                    If None, allows all methods.
            settings: Optional dictionary of settings to be added to the container when handling this route.
            container: Optional container instance to use for dependency injection. If not provided, uses the global container.

        Examples:
            >>> router.add_route("/users", user_handler, ["GET", "POST"])
            >>> router.add_route("/items", ItemRoute, settings={"db_table": "items"})
        """
        match handler:
            case type() as route if hasattr(route, "__method_handlers__") and hasattr(
                route, "__form_handlers__"
            ):
                # Keep track of which paths are mapped to which Route classes
                if route not in self._route_class_paths:
                    self._route_class_paths[route] = []
                self._route_class_paths[route].append(path)

                # Initialize the Route class directly to avoid container.call issues
                # We'll still use a container branch to handle RouteSettings
                if container is None:
                    # Create a new container from scratch if none was provided
                    from bevy import get_registry

                    container = get_registry().create_container()

                with container.branch() as branch_container:
                    branch_container.add(RouteSettings, RouteSettings(**settings or {}))
                    # Create route instance directly instead of using container.call
                    try:
                        route_instance = route()
                    except Exception as e:
                        import logging

                        logging.getLogger(__name__).error(
                            f"Error initializing route {route}: {e}"
                        )
                        raise

                methods = (
                    route.__method_handlers__.keys() | route.__form_handlers__.keys()
                )
                # Store these settings for the actual path
                self._route_settings[path] = settings or {}
                self.add_route(
                    path, route_instance.__call__, list(methods), settings=settings
                )

            case _:
                normalized_methods = (
                    frozenset(m.upper() for m in methods) if methods else None
                )
                self._routes.append((path, normalized_methods, handler, settings or {}))

    def add_websocket(
        self,
        path: str,
        handler: "Callable[..., Awaitable[Any]]",
        *,
        settings: dict[str, Any] = None,
    ):
        """Adds a WebSocket route to this router.

        Args:
            path: The path pattern for the WebSocket route.
            handler: An async WebSocket handler function that accepts a WebSocket parameter.
            settings: Optional dictionary of settings to be added to the container when handling this route.

        Examples:
            >>> async def echo_handler(websocket):
            ...     async for message in websocket:
            ...         await websocket.send(message)
            >>> router.add_websocket("/ws", echo_handler)

            >>> # With settings
            >>> router.add_websocket("/ws", echo_handler, settings={"auth_required": True})
        """
        self._websocket_routes.append((path, handler, settings or {}))

    def add_router(self, router: "Router"):
        """Adds a sub-router. Sub-routers are checked before the current router's own routes.
        Later added sub-routers are checked first (LIFO order for matching)."""
        self._sub_routers.append(router)

    def mount(self, path: str, router: "Router"):
        """Mounts a router at a specific path.

        Unlike add_router which adds a router with full request path access,
        mount prefixes all routes in the mounted router with the given path.

        Args:
            path: The path prefix where the router should be mounted.
                 Should start with a '/' and not end with one.
            router: The router instance to mount at the specified path.

        Examples:
            >>> api_router = Router()
            >>> api_router.add_route("/users", users_handler)
            >>> main_router.mount("/api", api_router)
            # Now "/api/users" will be handled by users_handler
        """
        if not path.startswith("/"):
            path = "/" + path
        if path.endswith("/"):
            path = path[:-1]

        self._mounted_routers.append((path, router))

    def url_for(self, handler: Callable | type["routes.Route"], **kwargs) -> str:
        """Builds a URL for a registered route handler with the given path parameters.

        Args:
            handler: The route handler function or Route class for which to build a URL.
            **kwargs: Path parameters to substitute in the URL pattern.

        Returns:
            A URL string with path parameters filled in.

        Raises:
            ValueError: If the handler is not found in any router, or if required path
                       parameters are missing from kwargs.
        """
        # Import generation functions to avoid circular dependency
        # Import routes at runtime to avoid circular dependency
        import serv.routes as routes
        from serv.routing.generation import (
            url_for_function_handler,
            url_for_route_class,
        )

        # First check if handler is a Route class
        if isinstance(handler, type) and issubclass(handler, routes.Route):
            return url_for_route_class(
                self._route_class_paths,
                self._mounted_routers,
                self._sub_routers,
                handler,
                **kwargs,
            )

        # Handle methods on Route instances (less common case)
        elif hasattr(handler, "__self__"):
            if isinstance(handler.__self__, routes.Route):
                route_instance = handler.__self__
                handler = route_instance.__call__
                path = self._find_handler_path(handler)
                if not path:
                    raise ValueError(
                        f"Route instance method {handler.__name__} not found in any router"
                    )

                from serv.routing.generation import build_url_from_path

                return build_url_from_path(path, kwargs)

        # For function handlers
        else:
            return url_for_function_handler(
                self._routes,
                self._mounted_routers,
                self._sub_routers,
                handler,
                **kwargs,
            )

    def _find_handler_path(self, handler: Callable) -> str | None:
        """Finds the first path pattern for a given handler in this router."""
        from serv.routing.generation import find_handler_path

        return find_handler_path(self._routes, handler)

    def resolve_route(
        self, request_path: str, request_method: str
    ) -> tuple[Callable, dict[str, Any], dict[str, Any]] | None:
        """Recursively finds a handler for the given path and method.

        Args:
            request_path: The path of the incoming request.
            request_method: The HTTP method of the incoming request.

        Returns:
            A tuple of (handler_callable, path_parameters_dict, settings_dict) if a match is found.
            None if no route matches the path (results in a 404).

        Raises:
            HTTPMethodNotAllowedException: If one or more routes match the path but not the method,
                                           and no route matches both path and method.
        """
        from serv.routing.resolvers import resolve_http_route

        return resolve_http_route(
            request_path,
            request_method,
            self._mounted_routers,
            self._sub_routers,
            self._routes,
            self._settings,
            self._match_path,
        )

    def _match_path(
        self, request_path: str, path_pattern: str
    ) -> dict[str, Any] | None:
        """Performs path matching.
        Supports exact matches and path parameters with optional type hints.
        Supported types: {param}, {param:int}, {param:path}
        Returns a dict of path parameters if matched, else None.
        """
        from serv.routing.patterns import match_path

        return match_path(request_path, path_pattern)

    def resolve_websocket(
        self, request_path: str
    ) -> tuple[Callable, dict[str, Any], dict[str, Any]] | None:
        """Resolve a WebSocket route for the given path.

        Args:
            request_path: The WebSocket request path to match against registered routes.

        Returns:
            A tuple of (handler_callable, path_params, route_settings) if a matching
            WebSocket route is found, None otherwise.

        Examples:
            >>> handler, params, settings = router.resolve_websocket("/ws/user/123")
            >>> if handler:
            ...     # Handle WebSocket connection
            ...     await handler(websocket, **params)
        """
        from serv.routing.resolvers import resolve_websocket_route

        return resolve_websocket_route(
            request_path,
            self._mounted_routers,
            self._sub_routers,
            self._websocket_routes,
            self._settings,
            self._match_path,
        )


@injectable
def get_current_router(container: Inject[Container]) -> Router:
    """Retrieves the current request's root Router instance from the Bevy container."""
    try:
        return container.get(Router)
    except Exception as e:  # Bevy might raise a specific exception if not found
        raise RuntimeError(
            "Router not found in the current request container. Ensure it's added during request setup."
        ) from e
