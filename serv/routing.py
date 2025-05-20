import inspect
from typing import Callable, Awaitable, List, Dict, Any, Sequence, Type, overload
from bevy import dependency, inject
from bevy.containers import Container

from serv.requests import Request
from serv.exceptions import HTTPNotFoundException, HTTPMethodNotAllowedException
import serv.routes as routes


class Router:
    def __init__(self):
        # Stores tuples of (path_pattern, methods, handler_callable)
        self._routes: List[tuple[str, frozenset[str] | None, Callable]] = []
        # Stores mapping of (route_class -> path_pattern) for url_for lookups
        self._route_class_paths: Dict[Type[routes.Route], str] = {}
        # Stores tuples of (mount_path, router_instance)
        self._mounted_routers: List[tuple[str, "Router"]] = []
        self._sub_routers: List[Router] = []

    @overload
    def add_route(self, path: str, handler: "Type[routes.Route]"):
        ...

    @overload
    def add_route(self, path: str, handler: "Callable[..., Awaitable[Any]]", methods: Sequence[str] | None = None):
        ...

    def add_route(self, path: str, handler: "Callable[..., Awaitable[Any]] | Type[routes.Route]", methods: Sequence[str] | None = None):
        """Adds a route to this router.

        This method can handle both direct route handlers and Route objects. For Route objects,
        it will automatically register all method and form handlers defined in the route.

        Args:
            path: The path pattern for the route.
            handler: Either a Route object or an async handler function.
            methods: A list of HTTP methods (e.g., ['GET', 'POST']). Only used when handler is a function.
                    If None, allows all methods.

        Examples:
            >>> router.add_route("/users", user_handler, ["GET", "POST"])
            >>> router.add_route("/items", ItemRoute)
        """
        match handler:
            case type() as route if issubclass(route, routes.Route):
                # Store the original route class for url_for lookups
                self._route_class_paths[route] = path
                
                # Create instance and register its __call__ method as usual
                route_instance = route()
                methods = route.__method_handlers__.keys() | route.__form_handlers__.keys()
                self.add_route(path, route_instance.__call__, methods)
                
            case _:
                normalized_methods = frozenset(m.upper() for m in methods) if methods else None
                self._routes.append((path, normalized_methods, handler))

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
        if not path.startswith('/'):
            path = '/' + path
        if path.endswith('/'):
            path = path[:-1]
            
        self._mounted_routers.append((path, router))

    def url_for(self, handler: Callable | Type[routes.Route], **kwargs) -> str:
        """Builds a URL for a registered route handler with the given path parameters.
        
        Args:
            handler: The route handler function, a method of a Route class, or a Route class itself
            **kwargs: Path parameters to substitute in the URL pattern
            
        Returns:
            A URL string with path parameters substituted
            
        Raises:
            ValueError: If the handler is not found or if required path parameters are missing
            
        Examples:
            >>> # Function handler
            >>> router.url_for(show_user, id=123)
            "/user/123"
            >>>
            >>> # Route class directly
            >>> router.url_for(UserProfileRoute, username="johndoe")
            "/users/johndoe"
        """
        # First check if handler is a Route class
        if isinstance(handler, type) and issubclass(handler, routes.Route):
            # Look for route class in the _route_class_paths dictionary
            if handler in self._route_class_paths:
                path = self._route_class_paths[handler]
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
                
                raise ValueError(f"Route class {handler.__name__} not found in any router")
        
        # Handle methods on Route instances (less common case)
        elif hasattr(handler, '__self__') and isinstance(handler.__self__, routes.Route):
            route_instance = handler.__self__
            handler = route_instance.__call__
            path = self._find_handler_path(handler)
            if not path:
                raise ValueError(f"Route instance method {handler.__name__} not found in any router")
        
        # For function handlers
        else:
            # Try to find the handler and its path
            path = self._find_handler_path(handler)
            if not path:
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
        
        # Insert path parameters
        parts = path.split('/')
        result_parts = []
        
        for part in parts:
            if part.startswith('{') and part.endswith('}'):
                param_name = part[1:-1]
                if param_name not in kwargs:
                    raise ValueError(f"Missing required path parameter: {param_name}")
                result_parts.append(str(kwargs[param_name]))
            else:
                result_parts.append(part)
        
        return '/' + '/'.join(p for p in result_parts if p)

    def _find_handler_path(self, handler: Callable) -> str | None:
        """Finds the path pattern for a given handler in this router."""
        for path, _, route_handler in self._routes:
            if route_handler == handler:
                return path
        return None

    def resolve_route(self, request_path: str, request_method: str) -> tuple[Callable, Dict[str, Any]] | None:
        """Recursively finds a handler for the given path and method.

        Args:
            request_path: The path of the incoming request.
            request_method: The HTTP method of the incoming request.

        Returns:
            A tuple of (handler_callable, path_parameters_dict) if a match is found.
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
                sub_path = request_path[len(mount_path):]
                if not sub_path:
                    sub_path = "/"
                elif not sub_path.startswith("/"):
                    sub_path = "/" + sub_path
                
                try:
                    resolved_in_mounted = mounted_router.resolve_route(sub_path, request_method)
                    if resolved_in_mounted:
                        return resolved_in_mounted  # Handler found and method matched in mounted router
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
                    return resolved_in_sub  # Handler found and method matched in sub-router
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
        for path_pattern, route_specific_methods, handler_callable in self._routes:
            match_info = self._match_path(request_path, path_pattern)
            if match_info is not None:  # Path matches
                found_path_match_but_not_method = True # Mark that we at least matched the path
                if route_specific_methods is None or request_method.upper() in route_specific_methods:
                    # Path and method match
                    return handler_callable, match_info
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
                allowed_methods=list(collected_allowed_methods)
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

    def _match_path(self, request_path: str, path_pattern: str) -> Dict[str, Any] | None:
        """Performs path matching. 
        Currently supports exact matches and simple {param} captures.
        Returns a dict of path parameters if matched, else None.
        """
        # Basic exact match for now, can be expanded for path parameters
        pattern_parts = path_pattern.strip("/").split("/")
        request_parts = request_path.strip("/").split("/")

        if len(pattern_parts) != len(request_parts):
            return None

        params = {}
        for p_part, r_part in zip(pattern_parts, request_parts):
            if p_part.startswith("{") and p_part.endswith("}"):
                param_name = p_part[1:-1]
                params[param_name] = r_part
            elif p_part != r_part:
                return None
        
        return params


@inject
def get_current_router(container: Container = dependency()) -> Router:
    """Retrieves the current request's root Router instance from the Bevy container."""
    try:
        return container.get(Router)
    except Exception as e: # Bevy might raise a specific exception if not found
        raise RuntimeError("Router not found in the current request container. Ensure it's added during request setup.") from e 