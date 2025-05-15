import inspect
from typing import Callable, Awaitable, List, Dict, Any, Sequence
from bevy import dependency, inject
from bevy.containers import Container

from serv.requests import Request
from serv.exceptions import HTTPNotFoundException, HTTPMethodNotAllowedException


class Router:
    def __init__(self):
        # Stores tuples of (path_pattern, methods, handler_callable)
        self._routes: List[tuple[str, frozenset[str] | None, Callable]] = []
        self._sub_routers: List[Router] = []

    def add_route(self, path: str, handler: Callable[..., Awaitable[Any]], methods: Sequence[str] | None = None):
        """Adds a route to this router.

        Args:
            path: The path pattern for the route.
            handler: The asynchronous handler function for the route.
            methods: A list of HTTP methods (e.g., ['GET', 'POST']). If None, allows all methods.
        """
        normalized_methods = frozenset(m.upper() for m in methods) if methods else None
        self._routes.append((path, normalized_methods, handler))

    def add_router(self, router: "Router"):
        """Adds a sub-router. Sub-routers are checked before the current router's own routes.
           Later added sub-routers are checked first (LIFO order for matching)."""
        self._sub_routers.append(router)

    def resolve_route(self, request_path: str, request_method: str) -> tuple[Callable, Dict[str, Any]] | None:
        """Recursively finds a handler for the given path and method.

        Args:
            request_path: The path of the incoming request.
            request_method: The HTTP method of the incoming request.

        Returns:
            A tuple of (handler_callable, path_parameters_dict) if a match is found.
            None if no route matches the path.
        
        Raises:
            HTTPMethodNotAllowedException: If a route matches the path but not the method.
        """
        # 1. Check sub-routers in reverse order of addition (LIFO for matching)
        for sub_router in reversed(self._sub_routers):
            try:
                resolved_in_sub = sub_router.resolve_route(request_path, request_method)
                if resolved_in_sub:
                    return resolved_in_sub  # Handler found and method matched in sub-router
            except HTTPMethodNotAllowedException as e:
                # If a sub-router definitively says "Method Not Allowed" for a path it matched,
                # this decision is final for that branch of the routing tree.
                raise e

        # 2. Check own routes
        for path_pattern, allowed_methods, handler_callable in self._routes:
            match_info = self._match_path(request_path, path_pattern)
            if match_info is not None:  # Path matches
                if allowed_methods is None or request_method.upper() in allowed_methods:
                    # Path and method match
                    return handler_callable, match_info
                else:
                    # Path matches, but method is not allowed for this specific route.
                    # This is a definitive 405 for this path if no other route (e.g. in other sub-routers
                    # that were not tried yet, or sibling routers if this was a sub-router call) matches.
                    raise HTTPMethodNotAllowedException(
                        f"Method {request_method} not allowed for path matching pattern {path_pattern}",
                        allowed_methods=list(allowed_methods) if allowed_methods else []
                    )
        
        # 3. If no route matched the path in this router or its sub-routers (that didn't raise 405)
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