"""Handler method decorators for Serv routing.

This module provides the decorator system for marking route handler methods
with HTTP methods, enabling the Route class to automatically discover and
register appropriate handlers for incoming requests.
"""

from functools import wraps


class _HandleDecorator:
    """Decorator class for marking route handler methods with HTTP methods.

    This decorator marks methods as handlers for specific HTTP methods,
    allowing the Route class to automatically discover them during registration.

    Examples:
        Basic usage:

        ```python
        class UserRoute(Route):
            @handle.GET
            async def get_user(self, request: GetRequest) -> str:
                return "User profile"

            @handle.POST
            async def create_user(self, request: PostRequest) -> str:
                return "User created"
        ```

        Combined methods:

        ```python
        class UserRoute(Route):
            @handle.GET | handle.HEAD
            async def get_user_info(self, request: GetRequest) -> str:
                return "User info available for GET and HEAD"
        ```
    """

    def __init__(self, methods: set[str]):
        """Initialize the decorator with a set of HTTP methods.

        Args:
            methods: Set of HTTP method names (e.g., {"GET", "POST"})
        """
        self.methods = methods

    def __call__(self, func):
        """Apply the decorator to a function.

        Args:
            func: The function to decorate

        Returns:
            The decorated function with __handle_methods__ attribute
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Store the HTTP methods this handler supports
        wrapper.__handle_methods__ = self.methods
        return wrapper

    def __or__(self, other):
        """Support for @handle.GET | handle.POST syntax.

        Args:
            other: Another _HandleDecorator instance

        Returns:
            A new _HandleDecorator with combined methods
        """
        if isinstance(other, _HandleDecorator):
            return _HandleDecorator(self.methods | other.methods)
        return NotImplemented


class _HandleRegistry:
    """Registry that provides method decorators like @handle.GET, @handle.POST.

    This class creates decorator instances for each HTTP method, providing
    a clean API for marking route handler methods.

    Attributes:
        GET: Decorator for GET requests
        POST: Decorator for POST requests
        PUT: Decorator for PUT requests
        DELETE: Decorator for DELETE requests
        PATCH: Decorator for PATCH requests
        OPTIONS: Decorator for OPTIONS requests
        HEAD: Decorator for HEAD requests
        FORM: Special decorator for form handling

    Examples:
        Standard HTTP methods:

        ```python
        class APIRoute(Route):
            @handle.GET
            async def get_data(self, request: GetRequest):
                return {"data": "value"}

            @handle.POST
            async def create_data(self, request: PostRequest):
                return {"created": True}

            @handle.PUT
            async def update_data(self, request: PutRequest):
                return {"updated": True}

            @handle.DELETE
            async def delete_data(self, request: DeleteRequest):
                return {"deleted": True}
        ```

        Form handling:

        ```python
        class FormRoute(Route):
            @handle.FORM
            async def process_form(self, form: UserForm):
                # Handle form submission
                return {"form_processed": True}
        ```

        Multiple methods:

        ```python
        class FlexibleRoute(Route):
            @handle.GET | handle.POST
            async def flexible_handler(self, request: Request):
                if request.method == "GET":
                    return "Getting data"
                else:
                    return "Creating data"
        ```
    """

    def __init__(self):
        """Initialize the registry with standard HTTP method decorators."""
        # Create decorator instances for each HTTP method
        self.GET = _HandleDecorator({"GET"})
        self.POST = _HandleDecorator({"POST"})
        self.PUT = _HandleDecorator({"PUT"})
        self.DELETE = _HandleDecorator({"DELETE"})
        self.PATCH = _HandleDecorator({"PATCH"})
        self.OPTIONS = _HandleDecorator({"OPTIONS"})
        self.HEAD = _HandleDecorator({"HEAD"})
        self.FORM = _HandleDecorator({"FORM"})  # Special form handler


# Create the global handle instance
handle = _HandleRegistry()

# Export the main components
__all__ = ["handle", "_HandleDecorator", "_HandleRegistry"]
