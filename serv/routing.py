from collections.abc import Awaitable, Callable, Sequence
from typing import Any, dataclass_transform, overload

from bevy import dependency, inject
from bevy.containers import Container

import serv.routes as routes
from serv.exceptions import HTTPMethodNotAllowedException, HTTPNotFoundException


@dataclass_transform()
class RouteSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Router:
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
        from serv.routing import Router

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
        self._websocket_routes: list[
            tuple[str, Callable, dict[str, Any]]
        ] = []
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
                    branch_container.instances[RouteSettings] = RouteSettings(
                        **settings or {}
                    )
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

    def url_for(self, handler: Callable | type[routes.Route], **kwargs) -> str:
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
        # First check if handler is a Route class
        if isinstance(handler, type) and issubclass(handler, routes.Route):
            # Look for route class in the _route_class_paths dictionary
            if handler in self._route_class_paths:
                path_list = self._route_class_paths[handler]

                # Find the best matching path based on provided kwargs
                path = self._find_best_matching_path(path_list, kwargs)
                if not path:
                    # If no path can be fully satisfied with the provided kwargs,
                    # use the most recently added path (last in the list)
                    path = path_list[-1]
            else:
                # If not found directly, check mounted routers
                for mount_path, mounted_router in self._mounted_routers:
                    try:
                        sub_path = mounted_router.url_for(handler, **kwargs)
                        return f"{mount_path}{sub_path}"
                    except ValueError:
                        continue

                # Check sub-routers
                for sub_router in self._sub_routers:
                    try:
                        return sub_router.url_for(handler, **kwargs)
                    except ValueError:
                        continue

                raise ValueError(
                    f"Route class {handler.__name__} not found in any router"
                )

        # Handle methods on Route instances (less common case)
        elif hasattr(handler, "__self__") and isinstance(
            handler.__self__, routes.Route
        ):
            route_instance = handler.__self__
            handler = route_instance.__call__
            path = self._find_handler_path(handler)
            if not path:
                raise ValueError(
                    f"Route instance method {handler.__name__} not found in any router"
                )

        # For function handlers
        else:
            # Try to find all paths for this handler
            paths = self._find_all_handler_paths(handler)
            if not paths:
                # If not found directly, check mounted routers
                for mount_path, mounted_router in self._mounted_routers:
                    try:
                        sub_path = mounted_router.url_for(handler, **kwargs)
                        return f"{mount_path}{sub_path}"
                    except ValueError:
                        continue

                # If not found in mounted routers, check sub-routers
                for sub_router in self._sub_routers:
                    try:
                        return sub_router.url_for(handler, **kwargs)
                    except ValueError:
                        continue

                raise ValueError(f"Handler {handler.__name__} not found in any router")

            # Try to find the best path based on the provided kwargs
            path = self._find_best_matching_path(paths, kwargs)
            if not path:
                # If no path can be fully satisfied, use the last registered path
                path = paths[-1]

        # Try to build the URL with the selected path
        # If the required parameters aren't in kwargs, we'll need to try other paths
        try:
            return self._build_url_from_path(path, kwargs)
        except ValueError as e:
            if isinstance(handler, type) and issubclass(handler, routes.Route):
                # For Route classes, try other paths if available
                path_list = self._route_class_paths[handler]
                for alt_path in reversed(path_list):
                    if alt_path != path:
                        try:
                            return self._build_url_from_path(alt_path, kwargs)
                        except ValueError:
                            continue

            elif paths and len(paths) > 1:
                # For function handlers, try other paths if available
                for alt_path in reversed(paths):
                    if alt_path != path:
                        try:
                            return self._build_url_from_path(alt_path, kwargs)
                        except ValueError:
                            continue

            # If we get here, no path could be satisfied with the provided kwargs
            raise e

    def _build_url_from_path(self, path: str, kwargs: dict) -> str:
        """Build a URL by substituting path parameters from kwargs."""
        parts = path.split("/")
        result_parts = []

        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                param_name = part[1:-1]
                if param_name not in kwargs:
                    raise ValueError(f"Missing required path parameter: {param_name}")
                result_parts.append(str(kwargs[param_name]))
            else:
                result_parts.append(part)

        return "/" + "/".join(p for p in result_parts if p)

    def _find_all_handler_paths(self, handler: Callable) -> list[str]:
        """Finds all path patterns for a given handler in this router."""
        return [
            path
            for path, _, route_handler, _ in self._routes
            if route_handler == handler
        ]

    def _find_best_matching_path(self, paths: list[str], kwargs: dict) -> str | None:
        """Find the best matching path based on the provided kwargs.

        This method tries to find a path where all required parameters are provided in kwargs.
        It prioritizes:
        1. Paths where all parameters are provided and the most parameters are used
        2. The most recently added path (last in the list)

        If no path can be fully satisfied, it returns None.
        """
        valid_paths = []

        for path in paths:
            param_names = [
                part[1:-1]
                for part in path.split("/")
                if part.startswith("{") and part.endswith("}")
            ]

            # Check if all parameters for this path are provided
            if all(param in kwargs for param in param_names):
                # Score is based on how many parameters are used by this path
                valid_paths.append((path, len(param_names)))

        if not valid_paths:
            return None

        # Return the path with the most parameters (to use as many kwargs as possible)
        valid_paths.sort(key=lambda x: x[1], reverse=True)
        return valid_paths[0][0]

    def _find_handler_path(self, handler: Callable) -> str | None:
        """Finds the first path pattern for a given handler in this router."""
        for path, _, route_handler, _ in self._routes:
            if route_handler == handler:
                return path
        return None

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
        collected_allowed_methods: set[str] = set()
        found_path_match_but_not_method = False

        # 1. Check mounted routers first
        for mount_path, mounted_router in self._mounted_routers:
            if request_path.startswith(mount_path):
                # Strip the mount path prefix for the mounted router
                sub_path = request_path[len(mount_path) :]
                if not sub_path:
                    sub_path = "/"
                elif not sub_path.startswith("/"):
                    sub_path = "/" + sub_path

                try:
                    resolved_in_mounted = mounted_router.resolve_route(
                        sub_path, request_method
                    )
                    if resolved_in_mounted:
                        handler, params, settings = resolved_in_mounted
                        # Merge router settings with any more specific settings
                        merged_settings = {
                            **self._settings,
                            **mounted_router._settings,
                            **settings,
                        }
                        return handler, params, merged_settings
                except HTTPMethodNotAllowedException as e:
                    # Mounted router matched the path but not the method
                    collected_allowed_methods.update(e.allowed_methods)
                    found_path_match_but_not_method = True
                except HTTPNotFoundException:
                    # Mounted router did not find the path. Continue search.
                    pass

        # 2. Check sub-routers in reverse order of addition (LIFO for matching)
        for sub_router in reversed(self._sub_routers):
            try:
                resolved_in_sub = sub_router.resolve_route(request_path, request_method)
                if resolved_in_sub:
                    handler, params, settings = resolved_in_sub
                    # Merge router settings with any more specific settings
                    merged_settings = {
                        **self._settings,
                        **sub_router._settings,
                        **settings,
                    }
                    return handler, params, merged_settings
            except HTTPMethodNotAllowedException as e:
                # Sub-router matched the path but not the method.
                # Collect its allowed methods and mark that a path match occurred.
                collected_allowed_methods.update(e.allowed_methods)
                found_path_match_but_not_method = True
                # Continue searching other sub-routers or parent's direct routes.
            except HTTPNotFoundException:
                # Sub-router did not find the path at all. Continue search.
                pass

        # 3. Check own routes
        for (
            path_pattern,
            route_specific_methods,
            handler_callable,
            route_settings,
        ) in self._routes:
            match_info = self._match_path(request_path, path_pattern)
            if match_info is not None:  # Path matches
                found_path_match_but_not_method = (
                    True  # Mark that we at least matched the path
                )
                if (
                    route_specific_methods is None
                    or request_method.upper() in route_specific_methods
                ):
                    # Path and method match
                    # Merge router settings with route settings
                    merged_settings = {**self._settings, **route_settings}
                    return handler_callable, match_info, merged_settings
                else:
                    # Path matches, but method is not allowed for this specific route.
                    # Collect allowed methods.
                    if route_specific_methods:
                        collected_allowed_methods.update(route_specific_methods)

        # 4. After checking all mounted routers, sub-routers and own routes:
        if found_path_match_but_not_method and collected_allowed_methods:
            # We found one or more path matches, but no method matches for that path.
            # And we have a list of methods that *would* have been allowed.
            raise HTTPMethodNotAllowedException(
                f"Method {request_method} not allowed for {request_path}",
                allowed_methods=list(collected_allowed_methods),
            )

        # If no path match was found at all, or if path matched but no methods were ever defined for it
        # (e.g. route_specific_methods was None and it wasn't a match, which is unlikely with current logic
        # but covering bases if collected_allowed_methods is empty despite found_path_match_but_not_method)
        if found_path_match_but_not_method and not collected_allowed_methods:
            # This case implies a path was matched by a route that allows ALL methods (None),
            # but the request_method somehow didn't trigger the "return handler_callable, match_info"
            # This shouldn't happen if request_method.upper() is in route_specific_methods when it's None.
            # For safety, if we matched a path but have no specific allowed methods to suggest,
            # it's still a method not allowed situation, but without specific 'Allow' header.
            # However, current logic means if route_specific_methods is None, it's an immediate match.
            # This path should ideally not be hit frequently.
            # To be safe, we will treat it as a 404 if no specific methods were collected.
            pass

        # No route matched the path at all, or a path was matched but it didn't lead to a 405 (e.g. ill-defined route).
        return None

    def _match_path(
        self, request_path: str, path_pattern: str
    ) -> dict[str, Any] | None:
        """Performs path matching.
        Supports exact matches and path parameters with optional type hints.
        Supported types: {param}, {param:int}, {param:path}
        Returns a dict of path parameters if matched, else None.
        """
        pattern_parts = path_pattern.strip("/").split("/")
        request_parts = request_path.strip("/").split("/")

        # Handle special case for path type parameters that can consume multiple segments
        if any("{" in part and ":path}" in part for part in pattern_parts):
            return self._match_path_with_path_type(request_path, path_pattern)

        if len(pattern_parts) != len(request_parts):
            return None

        params = {}
        for p_part, r_part in zip(pattern_parts, request_parts, strict=False):
            if "{" in p_part and "}" in p_part:
                # Handle parameters that might be embedded in text (like "v{version:int}")
                result = self._match_segment_with_params(p_part, r_part)
                if result is None:
                    return None
                params.update(result)
            elif p_part != r_part:
                return None

        return params

    def _match_segment_with_params(
        self, pattern_segment: str, request_segment: str
    ) -> dict[str, Any] | None:
        """Match a single path segment that may contain embedded parameters."""
        import re

        # Find all parameters in the pattern segment
        param_pattern = r"\{([^}]+)\}"
        params = {}

        # Build a regex pattern by replacing parameter placeholders
        regex_pattern = pattern_segment
        param_matches = re.finditer(param_pattern, pattern_segment)

        for match in reversed(list(param_matches)):  # Reverse to maintain indices
            param_spec = match.group(1)
            if ":" in param_spec:
                param_name, param_type = param_spec.split(":", 1)
                if param_type == "int":
                    # Replace with regex for integers
                    regex_pattern = (
                        regex_pattern[: match.start()]
                        + r"(\d+)"
                        + regex_pattern[match.end() :]
                    )
                elif param_type == "path":
                    # For path type in a segment, match everything
                    regex_pattern = (
                        regex_pattern[: match.start()]
                        + r"(.+)"
                        + regex_pattern[match.end() :]
                    )
                else:
                    # Default to matching non-slash characters
                    regex_pattern = (
                        regex_pattern[: match.start()]
                        + r"([^/]+)"
                        + regex_pattern[match.end() :]
                    )
            else:
                # Simple parameter, match non-slash characters
                regex_pattern = (
                    regex_pattern[: match.start()]
                    + r"([^/]+)"
                    + regex_pattern[match.end() :]
                )

        # Escape any remaining regex special characters in the pattern
        regex_pattern = regex_pattern.replace(".", r"\.")
        regex_pattern = "^" + regex_pattern + "$"

        # Try to match the request segment
        match = re.match(regex_pattern, request_segment)
        if not match:
            return None

        # Extract parameter values
        param_matches = list(re.finditer(param_pattern, pattern_segment))
        for i, param_match in enumerate(param_matches):
            param_spec = param_match.group(1)
            value = match.group(i + 1)

            if ":" in param_spec:
                param_name, param_type = param_spec.split(":", 1)
                try:
                    if param_type == "int":
                        params[param_name] = int(value)
                    elif param_type == "path":
                        params[param_name] = value
                    else:
                        params[param_name] = value
                except ValueError:
                    return None
            else:
                params[param_spec] = value

        return params

    def _match_path_with_path_type(
        self, request_path: str, path_pattern: str
    ) -> dict[str, Any] | None:
        """Handle path patterns with path type parameters that can consume multiple segments."""
        pattern_parts = path_pattern.strip("/").split("/")
        request_parts = request_path.strip("/").split("/")

        params = {}
        pattern_idx = 0
        request_idx = 0

        while pattern_idx < len(pattern_parts) and request_idx < len(request_parts):
            p_part = pattern_parts[pattern_idx]

            if p_part.startswith("{") and p_part.endswith("}"):
                param_spec = p_part[1:-1]
                if ":" in param_spec:
                    param_name, param_type = param_spec.split(":", 1)
                    if param_type == "path":
                        # Path type consumes remaining segments
                        remaining_pattern = len(pattern_parts) - pattern_idx - 1
                        if remaining_pattern == 0:
                            # This is the last part, consume all remaining request parts
                            path_value = "/".join(request_parts[request_idx:])
                            params[param_name] = path_value
                            return params
                        else:
                            # Calculate how many segments to consume
                            remaining_request = len(request_parts) - request_idx
                            segments_to_consume = remaining_request - remaining_pattern
                            if segments_to_consume < 1:
                                return None
                            path_value = "/".join(
                                request_parts[
                                    request_idx : request_idx + segments_to_consume
                                ]
                            )
                            params[param_name] = path_value
                            request_idx += segments_to_consume
                    elif param_type == "int":
                        try:
                            params[param_name] = int(request_parts[request_idx])
                        except ValueError:
                            return None
                        request_idx += 1
                    else:
                        params[param_name] = request_parts[request_idx]
                        request_idx += 1
                else:
                    params[param_spec] = request_parts[request_idx]
                    request_idx += 1
            else:
                # Exact match required
                if p_part != request_parts[request_idx]:
                    return None
                request_idx += 1

            pattern_idx += 1

        # Check if we consumed all parts
        if pattern_idx == len(pattern_parts) and request_idx == len(request_parts):
            return params

        return None

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
        # First check sub-routers (they take precedence)
        for sub_router in reversed(self._sub_routers):
            result = sub_router.resolve_websocket(request_path)
            if result:
                return result

        # Check mounted routers
        for mount_path, mounted_router in self._mounted_routers:
            if request_path.startswith(mount_path):
                # Remove the mount path prefix before checking the mounted router
                relative_path = request_path[len(mount_path) :] or "/"
                result = mounted_router.resolve_websocket(relative_path)
                if result:
                    return result

        # Check our own WebSocket routes
        for path_pattern, handler, settings in self._websocket_routes:
            path_params = self._match_path(request_path, path_pattern)
            if path_params is not None:
                # Merge router-level settings with route-specific settings
                merged_settings = {**self._settings, **settings}
                return handler, path_params, merged_settings

        return None


@inject
def get_current_router(container: Container = dependency()) -> Router:
    """Retrieves the current request's root Router instance from the Bevy container."""
    try:
        return container.get(Router)
    except Exception as e:  # Bevy might raise a specific exception if not found
        raise RuntimeError(
            "Router not found in the current request container. Ensure it's added during request setup."
        ) from e
