class ServException(Exception):
    """Base exception for Serv application."""
    status_code = 500  # Default status code


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