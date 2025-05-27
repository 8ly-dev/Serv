class ServException(Exception):
    """Base exception class for all Serv application errors.

    This is the root exception class for the Serv framework. All framework-specific
    exceptions inherit from this class, providing a consistent interface for error
    handling and HTTP status code mapping.

    Attributes:
        status_code: HTTP status code associated with this exception (default: 500).
        message: Human-readable error message.

    Examples:
        Creating custom exceptions:

        ```python
        class ValidationError(ServException):
            status_code = 400

            def __init__(self, field: str, value: str):
                super().__init__(f"Invalid value '{value}' for field '{field}'")
                self.field = field
                self.value = value

        class AuthenticationError(ServException):
            status_code = 401

            def __init__(self, message: str = "Authentication required"):
                super().__init__(message)
        ```

        Using in route handlers:

        ```python
        from serv.routes import Route, PostRequest
        from serv.exceptions import HTTPBadRequestException

        class UserRoute(Route):
            async def handle_post(self, request: PostRequest):
                data = await request.json()
                if not data.get("email"):
                    raise HTTPBadRequestException("Email is required")
                # Process user creation...
        ```

        Handling in error handlers:

        ```python
        async def custom_error_handler(
            error: ServException,
            response: ResponseBuilder = dependency()
        ):
            response.set_status(error.status_code)
            response.content_type("application/json")
            response.body({
                "error": error.message,
                "status_code": error.status_code
            })

        app.add_error_handler(ServException, custom_error_handler)
        ```
    """

    status_code = 500  # Default status code
    message: str  # Type hint for the message attribute

    def __init__(self, message: str | None = None, *args):
        super().__init__(message, *args)  # Pass message to parent Exception
        # Set self.message: use provided message, or if None, try to use the first arg (if any)
        # or fall back to a default string representation of the class name.
        if message is not None:
            self.message = message
        elif args and args[0]:  # If message is None but other args are present
            self.message = str(args[0])
        else:  # Fallback if no message-like argument is provided
            self.message = self.__class__.__name__


class HTTPNotFoundException(ServException):
    """Raised when a requested route or resource is not found (HTTP 404).

    This exception is automatically raised by the router when no matching
    route is found for the requested path. It can also be raised manually
    in route handlers when a specific resource is not found.

    Examples:
        Automatic usage by router:

        ```python
        # GET /nonexistent-path -> HTTPNotFoundException
        ```

        Manual usage in route handlers:

        ```python
        from serv.routes import Route, GetRequest
        from serv.exceptions import HTTPNotFoundException

        class UserRoute(Route):
            async def handle_get(self, request: GetRequest):
                user_id = request.path_params.get("id")
                user = await self.get_user(user_id)
                if not user:
                    raise HTTPNotFoundException(f"User {user_id} not found")
                return user
        ```
    """

    status_code = 404


class HTTPMethodNotAllowedException(ServException):
    """Raised when a route exists but doesn't support the requested HTTP method (HTTP 405).

    This exception is automatically raised when a route is found but the specific
    HTTP method (GET, POST, etc.) is not implemented by the route handler.

    Attributes:
        allowed_methods: List of HTTP methods that are supported by the route.

    Examples:
        Automatic usage by router:

        ```python
        # If a route only supports GET but receives POST
        # -> HTTPMethodNotAllowedException with allowed_methods=["GET"]
        ```

        Manual usage in route handlers:

        ```python
        from serv.exceptions import HTTPMethodNotAllowedException

        class ApiRoute(Route):
            async def handle_get(self, request: GetRequest):
                if not self.is_read_only_mode():
                    return {"data": "some data"}
                else:
                    raise HTTPMethodNotAllowedException(
                        "API is in read-only mode",
                        allowed_methods=["GET"]
                    )
        ```
    """

    status_code = 405

    def __init__(self, message: str, allowed_methods: list[str]):
        super().__init__(message)
        self.allowed_methods = allowed_methods


class HTTPBadRequestException(ServException):
    """Raised for malformed requests or client errors (HTTP 400).

    This exception should be raised when the client sends a request that
    cannot be processed due to invalid syntax, missing required parameters,
    or other client-side errors.

    Examples:
        Validation errors:

        ```python
        from serv.routes import Route, PostRequest
        from serv.exceptions import HTTPBadRequestException

        class UserRoute(Route):
            async def handle_post(self, request: PostRequest):
                data = await request.json()

                if not data.get("email"):
                    raise HTTPBadRequestException("Email field is required")

                if "@" not in data["email"]:
                    raise HTTPBadRequestException("Invalid email format")

                # Process valid request...
        ```

        Form validation:

        ```python
        class ContactForm(Form):
            name: str
            email: str
            message: str

        class ContactRoute(Route):
            async def handle_contact_form(self, form: ContactForm):
                if len(form.message) < 10:
                    raise HTTPBadRequestException("Message must be at least 10 characters")

                # Process form...
        ```
    """

    status_code = 400


# Add other common HTTP exceptions as needed, e.g.:
# class HTTPUnauthorizedException(ServException): status_code = 401
# class HTTPForbiddenException(ServException): status_code = 403
