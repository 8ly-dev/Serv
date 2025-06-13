"""Routing layer for Serv - URL patterns, route resolution, handlers."""

# Re-export from routing submodules
try:
    from serv.routing.router import Router
    from serv.routing.handlers import Route
    from serv.routing.decorators import handle
    
    # Also export useful routing utilities
    from serv.routing.patterns import match_path
    from serv.routing.generation import build_url_from_path
    from serv.routing.resolvers import resolve_http_route, resolve_websocket_route

    
    __all__ = [
        "Router",
        "Route",
        "handle",
        "match_path",
        "build_url_from_path", 
        "resolve_http_route",
        "resolve_websocket_route",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []
