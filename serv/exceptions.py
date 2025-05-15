class ServException(Exception):
    """Base exception for Serv application."""
    status_code = 500  # Default status code
    message: str # Type hint for the message attribute

    def __init__(self, message: str | None = None, *args):
        super().__init__(message, *args) # Pass message to parent Exception
        # Set self.message: use provided message, or if None, try to use the first arg (if any)
        # or fall back to a default string representation of the class name.
        if message is not None:
            self.message = message
        elif args and args[0]: # If message is None but other args are present
             self.message = str(args[0])
        else: # Fallback if no message-like argument is provided
             self.message = self.__class__.__name__ 


class HTTPNotFoundException(ServException):
    """Raised when a route is not found (404)."""
    status_code = 404


class HTTPMethodNotAllowedException(ServException):
    """Raised when a route is found but the method is not allowed (405)."""
    status_code = 405
    def __init__(self, message: str, allowed_methods: list[str]):
        super().__init__(message)
        self.allowed_methods = allowed_methods


class HTTPBadRequestException(ServException):
    """Raised for general client errors (400)."""
    status_code = 400

# Add other common HTTP exceptions as needed, e.g.:
# class HTTPUnauthorizedException(ServException): status_code = 401
# class HTTPForbiddenException(ServException): status_code = 403 