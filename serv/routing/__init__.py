"""Routing layer for Serv - URL patterns, route resolution, handlers."""

# Re-export from existing modules for backward compatibility
try:
    from serv._routing import Router
    from serv.routes import Route

    __all__ = [
        "Router",
        "Route",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []

# Import handle separately to avoid circular dependency
try:
    from serv.routing.decorators import handle
    __all__.append("handle")
except ImportError:
    pass
