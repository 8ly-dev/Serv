"""Route resolution logic for Serv routing.

This module provides functions for resolving HTTP and WebSocket routes,
handling path matching, method validation, and error scenarios (404/405).
"""

from collections.abc import Callable
from typing import Any

from serv.exceptions import HTTPMethodNotAllowedException, HTTPNotFoundException


def resolve_http_route(
    request_path: str,
    request_method: str,
    mounted_routers: list[tuple[str, "Router"]],
    sub_routers: list["Router"], 
    routes: list[tuple[str, list[str] | None, Callable, dict[str, Any]]],
    router_settings: dict[str, Any],
    match_path_func: Callable[[str, str], dict[str, Any] | None]
) -> tuple[Callable, dict[str, Any], dict[str, Any]] | None:
    """Resolve an HTTP route for the given path and method.
    
    This function implements the complete route resolution algorithm, checking
    mounted routers, sub-routers, and direct routes in the correct order.
    
    Args:
        request_path: The path of the incoming request
        request_method: The HTTP method of the incoming request
        mounted_routers: List of (mount_path, router) tuples
        sub_routers: List of sub-routers to check
        routes: List of route tuples (path, methods, handler, settings)
        router_settings: Router-level settings to merge
        match_path_func: Function to perform path pattern matching
        
    Returns:
        A tuple of (handler_callable, path_parameters_dict, settings_dict) if a match is found.
        None if no route matches the path (results in a 404).
        
    Raises:
        HTTPMethodNotAllowedException: If one or more routes match the path but not the method.
        
    Examples:
        >>> handler, params, settings = resolve_http_route(
        ...     "/users/123", "GET", [], [], 
        ...     [("/users/{id}", ["GET"], my_handler, {})],
        ...     {}, match_path
        ... )
        >>> if handler:
        ...     # Route found, call handler with params
        ...     await handler(**params)
    """
    collected_allowed_methods: set[str] = set()
    found_path_match_but_not_method = False

    # 1. Check mounted routers first
    for mount_path, mounted_router in mounted_routers:
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
                        **router_settings,
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
    for sub_router in reversed(sub_routers):
        try:
            resolved_in_sub = sub_router.resolve_route(request_path, request_method)
            if resolved_in_sub:
                handler, params, settings = resolved_in_sub
                # Merge router settings with any more specific settings
                merged_settings = {
                    **router_settings,
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
    ) in routes:
        match_info = match_path_func(request_path, path_pattern)
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
                merged_settings = {**router_settings, **route_settings}
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


def resolve_websocket_route(
    request_path: str,
    mounted_routers: list[tuple[str, "Router"]],
    sub_routers: list["Router"],
    websocket_routes: list[tuple[str, Callable, dict[str, Any]]],
    router_settings: dict[str, Any],
    match_path_func: Callable[[str, str], dict[str, Any] | None]
) -> tuple[Callable, dict[str, Any], dict[str, Any]] | None:
    """Resolve a WebSocket route for the given path.
    
    Args:
        request_path: The WebSocket request path to match against registered routes
        mounted_routers: List of (mount_path, router) tuples
        sub_routers: List of sub-routers to check
        websocket_routes: List of WebSocket route tuples (path, handler, settings)
        router_settings: Router-level settings to merge
        match_path_func: Function to perform path pattern matching
        
    Returns:
        A tuple of (handler_callable, path_params, route_settings) if a matching
        WebSocket route is found, None otherwise.
        
    Examples:
        >>> handler, params, settings = resolve_websocket_route(
        ...     "/ws/user/123", [], [],
        ...     [("/ws/user/{id}", ws_handler, {})],
        ...     {}, match_path
        ... )
        >>> if handler:
        ...     # Handle WebSocket connection
        ...     await handler(websocket, **params)
    """
    # First check sub-routers (they take precedence)
    for sub_router in reversed(sub_routers):
        result = sub_router.resolve_websocket(request_path)
        if result:
            return result

    # Check mounted routers
    for mount_path, mounted_router in mounted_routers:
        if request_path.startswith(mount_path):
            # Remove the mount path prefix before checking the mounted router
            relative_path = request_path[len(mount_path) :] or "/"
            result = mounted_router.resolve_websocket(relative_path)
            if result:
                return result

    # Check our own WebSocket routes
    for path_pattern, handler, settings in websocket_routes:
        path_params = match_path_func(request_path, path_pattern)
        if path_params is not None:
            # Merge router-level settings with route-specific settings
            merged_settings = {**router_settings, **settings}
            return handler, path_params, merged_settings

    return None


def check_method_allowed(
    path_pattern: str,
    route_methods: list[str] | None,
    request_method: str
) -> bool:
    """Check if a request method is allowed for a route.
    
    Args:
        path_pattern: The route path pattern
        route_methods: List of allowed methods for the route, or None for all methods
        request_method: The request method to check
        
    Returns:
        True if the method is allowed, False otherwise
        
    Examples:
        >>> check_method_allowed("/users", ["GET", "POST"], "GET")
        True
        
        >>> check_method_allowed("/users", ["GET", "POST"], "DELETE")
        False
        
        >>> check_method_allowed("/users", None, "ANY_METHOD")
        True  # None means all methods allowed
    """
    if route_methods is None:
        return True  # All methods allowed
    return request_method.upper() in route_methods


def collect_allowed_methods(
    routes: list[tuple[str, list[str] | None, Callable, dict[str, Any]]],
    request_path: str,
    match_path_func: Callable[[str, str], dict[str, Any] | None]
) -> set[str]:
    """Collect all allowed methods for routes that match the given path.
    
    Args:
        routes: List of route tuples (path, methods, handler, settings)
        request_path: The request path to check
        match_path_func: Function to perform path pattern matching
        
    Returns:
        Set of allowed HTTP methods for the path
        
    Examples:
        >>> routes = [
        ...     ("/users", ["GET", "POST"], handler1, {}),
        ...     ("/users", ["PUT"], handler2, {})
        ... ]
        >>> collect_allowed_methods(routes, "/users", match_path)
        {"GET", "POST", "PUT"}
    """
    allowed_methods = set()
    
    for path_pattern, route_methods, _, _ in routes:
        if match_path_func(request_path, path_pattern) is not None:
            if route_methods is not None:
                allowed_methods.update(route_methods)
                
    return allowed_methods