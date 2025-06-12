"""HTTP request classes and request handling utilities."""

from serv.requests import Request


class GetRequest(Request):
    """HTTP GET request type marker for dependency injection and route handling."""
    pass


class PostRequest(Request):
    """HTTP POST request type marker for dependency injection and route handling."""
    pass


class PutRequest(Request):
    """HTTP PUT request type marker for dependency injection and route handling."""
    pass


class DeleteRequest(Request):
    """HTTP DELETE request type marker for dependency injection and route handling."""
    pass


class PatchRequest(Request):
    """HTTP PATCH request type marker for dependency injection and route handling."""
    pass


class OptionsRequest(Request):
    """HTTP OPTIONS request type marker for dependency injection and route handling."""
    pass


class HeadRequest(Request):
    """HTTP HEAD request type marker for dependency injection and route handling."""
    pass


# Mapping from request class to HTTP method string
MethodMapping = {
    GetRequest: "GET",
    PostRequest: "POST", 
    PutRequest: "PUT",
    DeleteRequest: "DELETE",
    PatchRequest: "PATCH",
    OptionsRequest: "OPTIONS",
    HeadRequest: "HEAD",
}

__all__ = [
    "GetRequest",
    "PostRequest",
    "PutRequest", 
    "DeleteRequest",
    "PatchRequest",
    "OptionsRequest",
    "HeadRequest",
    "MethodMapping",
    "Request",  # Re-export base Request class
]