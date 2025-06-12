"""URL generation utilities for Serv routing.

This module provides functions for building URLs from route handlers and path patterns,
enabling reverse URL generation for registered routes.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import serv.routes as routes


def build_url_from_path(path: str, kwargs: dict[str, Any]) -> str:
    """Build a URL by substituting path parameters from kwargs.
    
    Args:
        path: The path pattern with parameter placeholders (e.g., "/users/{user_id}")
        kwargs: Dictionary containing parameter values
        
    Returns:
        A URL string with path parameters filled in
        
    Raises:
        ValueError: If required path parameters are missing from kwargs
        
    Examples:
        >>> build_url_from_path("/users/{user_id}", {"user_id": 123})
        "/users/123"
        
        >>> build_url_from_path("/api/v{version}/users/{user_id}", {"version": 1, "user_id": 123})
        "/api/v1/users/123"
        
        >>> build_url_from_path("/files/{path:path}", {"path": "docs/readme.txt"})
        "/files/docs/readme.txt"
    """
    parts = path.split("/")
    result_parts = []

    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            param_name = part[1:-1]
            # Handle typed parameters like {user_id:int}
            if ":" in param_name:
                param_name = param_name.split(":")[0]
            if param_name not in kwargs:
                raise ValueError(f"Missing required path parameter: {param_name}")
            result_parts.append(str(kwargs[param_name]))
        else:
            result_parts.append(part)

    return "/" + "/".join(p for p in result_parts if p)


def find_all_handler_paths(routes_list: list[tuple], handler: Callable) -> list[str]:
    """Find all path patterns for a given handler in a routes list.
    
    Args:
        routes_list: List of route tuples (path, methods, handler, settings)
        handler: The handler function to find paths for
        
    Returns:
        List of path patterns that map to the given handler
        
    Examples:
        >>> routes = [("/users", ["GET"], my_handler, {}), ("/people", ["GET"], my_handler, {})]
        >>> find_all_handler_paths(routes, my_handler)
        ["/users", "/people"]
    """
    return [
        path
        for path, _, route_handler, _ in routes_list
        if route_handler == handler
    ]


def find_best_matching_path(paths: list[str], kwargs: dict[str, Any]) -> str | None:
    """Find the best matching path based on the provided kwargs.

    This method tries to find a path where all required parameters are provided in kwargs.
    It prioritizes:
    1. Paths where all parameters are provided and the most parameters are used
    2. The most recently added path (last in the list)

    If no path can be fully satisfied, it returns None.
    
    Args:
        paths: List of path patterns to choose from
        kwargs: Dictionary of available parameters
        
    Returns:
        Best matching path pattern or None if no match
        
    Examples:
        >>> paths = ["/users/{id}", "/users/{id}/profile/{type}"]
        >>> find_best_matching_path(paths, {"id": 123, "type": "public"})
        "/users/{id}/profile/{type}"  # Uses more parameters
        
        >>> find_best_matching_path(paths, {"id": 123})
        "/users/{id}"  # Only one with all required parameters
    """
    valid_paths = []

    for path in paths:
        param_names = []
        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                param_spec = part[1:-1]
                # Handle typed parameters like {user_id:int}
                if ":" in param_spec:
                    param_name = param_spec.split(":")[0]
                else:
                    param_name = param_spec
                param_names.append(param_name)

        # Check if all parameters for this path are provided
        if all(param in kwargs for param in param_names):
            # Score is based on how many parameters are used by this path
            valid_paths.append((path, len(param_names)))

    if not valid_paths:
        return None

    # Return the path with the most parameters (to use as many kwargs as possible)
    valid_paths.sort(key=lambda x: x[1], reverse=True)
    return valid_paths[0][0]


def find_handler_path(routes_list: list[tuple], handler: Callable) -> str | None:
    """Find the first path pattern for a given handler in a routes list.
    
    Args:
        routes_list: List of route tuples (path, methods, handler, settings)
        handler: The handler function to find a path for
        
    Returns:
        First path pattern that maps to the given handler, or None if not found
        
    Examples:
        >>> routes = [("/users", ["GET"], my_handler, {}), ("/people", ["GET"], other_handler, {})]
        >>> find_handler_path(routes, my_handler)
        "/users"
    """
    for path, _, route_handler, _ in routes_list:
        if route_handler == handler:
            return path
    return None


def url_for_route_class(
    route_class_paths: dict[type, list[str]],
    mounted_routers: list[tuple],
    sub_routers: list,
    handler: type["routes.Route"],
    **kwargs
) -> str:
    """Build URL for a Route class.
    
    Args:
        route_class_paths: Dictionary mapping Route classes to their path patterns
        mounted_routers: List of (mount_path, router) tuples for mounted routers
        sub_routers: List of sub-routers to search
        handler: Route class to build URL for
        **kwargs: Path parameters
        
    Returns:
        URL string for the Route class
        
    Raises:
        ValueError: If route class not found or required parameters missing
    """
    # Import routes at runtime to avoid circular dependency
    import serv.routes as routes

    if not (isinstance(handler, type) and issubclass(handler, routes.Route)):
        raise ValueError("Handler must be a Route class")

    # Look for route class in the _route_class_paths dictionary
    if handler in route_class_paths:
        path_list = route_class_paths[handler]

        # Find the best matching path based on provided kwargs
        path = find_best_matching_path(path_list, kwargs)
        if not path:
            # If no path can be fully satisfied with the provided kwargs,
            # use the most recently added path (last in the list)
            path = path_list[-1]
        
        # Try to build the URL with the selected path
        # If the required parameters aren't in kwargs, we'll need to try other paths
        try:
            return build_url_from_path(path, kwargs)
        except ValueError:
            # For Route classes, try other paths if available
            for alt_path in reversed(path_list):
                if alt_path != path:
                    try:
                        return build_url_from_path(alt_path, kwargs)
                    except ValueError:
                        continue
            # Re-raise the original error if no path worked
            raise
    else:
        # If not found directly, check mounted routers
        for mount_path, mounted_router in mounted_routers:
            try:
                sub_path = mounted_router.url_for(handler, **kwargs)
                return f"{mount_path}{sub_path}"
            except ValueError:
                continue

        # Check sub-routers
        for sub_router in sub_routers:
            try:
                return sub_router.url_for(handler, **kwargs)
            except ValueError:
                continue

        raise ValueError(f"Route class {handler.__name__} not found in any router")


def url_for_function_handler(
    routes_list: list[tuple],
    mounted_routers: list[tuple],
    sub_routers: list,
    handler: Callable,
    **kwargs
) -> str:
    """Build URL for a function handler.
    
    Args:
        routes_list: List of route tuples (path, methods, handler, settings)
        mounted_routers: List of (mount_path, router) tuples for mounted routers
        sub_routers: List of sub-routers to search
        handler: Function handler to build URL for
        **kwargs: Path parameters
        
    Returns:
        URL string for the function handler
        
    Raises:
        ValueError: If handler not found or required parameters missing
    """
    # Try to find all paths for this handler
    paths = find_all_handler_paths(routes_list, handler)
    if not paths:
        # If not found directly, check mounted routers
        for mount_path, mounted_router in mounted_routers:
            try:
                sub_path = mounted_router.url_for(handler, **kwargs)
                return f"{mount_path}{sub_path}"
            except ValueError:
                continue

        # If not found in mounted routers, check sub-routers
        for sub_router in sub_routers:
            try:
                return sub_router.url_for(handler, **kwargs)
            except ValueError:
                continue

        raise ValueError(f"Handler {handler.__name__} not found in any router")

    # Try to find the best path based on the provided kwargs
    path = find_best_matching_path(paths, kwargs)
    if not path:
        # If no path can be fully satisfied, use the last registered path
        path = paths[-1]

    # Try to build the URL with the selected path
    try:
        return build_url_from_path(path, kwargs)
    except ValueError as e:
        # For function handlers, try other paths if available
        if len(paths) > 1:
            for alt_path in reversed(paths):
                if alt_path != path:
                    try:
                        return build_url_from_path(alt_path, kwargs)
                    except ValueError:
                        continue
        
        # If we get here, no path could be satisfied with the provided kwargs
        raise e