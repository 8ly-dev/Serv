"""Application layer for Serv - core app, middleware, extensions, lifecycle."""

# Re-export from existing modules for backward compatibility
try:
    from serv._app import App

    __all__ = [
        "App",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []
