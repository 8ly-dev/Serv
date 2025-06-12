"""Application layer for Serv - core app, middleware, extensions, lifecycle."""

# Re-export from existing modules for backward compatibility
try:
    from serv._app import App
    from serv.app.middleware import MiddlewareManager

    __all__ = [
        "App",
        "MiddlewareManager",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []
