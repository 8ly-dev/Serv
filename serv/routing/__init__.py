"""Routing layer for Serv - URL patterns, route resolution, handlers."""

# Re-export from existing modules for backward compatibility
try:
    from serv._routing import Router
    from serv.routing.handlers import Route
    from serv.routing.decorators import handle

    __all__ = [
        "Router",
        "Route",
        "handle",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []
