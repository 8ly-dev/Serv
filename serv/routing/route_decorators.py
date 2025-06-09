"""Route decorators for HTTP method handling."""

from functools import wraps


class _HandleDecorator:
    """Decorator class for marking route handler methods with HTTP methods."""

    def __init__(self, methods: set[str]):
        self.methods = methods

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__handle_methods__ = self.methods
        return wrapper

    def __or__(self, other):
        """Support for @handle.GET | handle.POST syntax"""
        if isinstance(other, _HandleDecorator):
            return _HandleDecorator(self.methods | other.methods)
        return NotImplemented


class _HandleRegistry:
    """Registry that provides method decorators like @handle.GET, @handle.POST"""

    def __init__(self):
        self.GET = _HandleDecorator({"GET"})
        self.POST = _HandleDecorator({"POST"})
        self.PUT = _HandleDecorator({"PUT"})
        self.DELETE = _HandleDecorator({"DELETE"})
        self.PATCH = _HandleDecorator({"PATCH"})
        self.OPTIONS = _HandleDecorator({"OPTIONS"})
        self.HEAD = _HandleDecorator({"HEAD"})
        self.FORM = _HandleDecorator({"FORM"})


# Global handle instance for decorators
handle = _HandleRegistry()
