"""Request type aliases for Serv applications."""

from .requests import Request


class GetRequest(Request):
    """Request for GET method."""

    pass


class PostRequest(Request):
    """Request for POST method."""

    pass


class PutRequest(Request):
    """Request for PUT method."""

    pass


class DeleteRequest(Request):
    """Request for DELETE method."""

    pass


class PatchRequest(Request):
    """Request for PATCH method."""

    pass


class OptionsRequest(Request):
    """Request for OPTIONS method."""

    pass


class HeadRequest(Request):
    """Request for HEAD method."""

    pass


# Method mapping for convenience
MethodMapping = {
    GetRequest: "GET",
    PostRequest: "POST",
    PutRequest: "PUT",
    DeleteRequest: "DELETE",
    PatchRequest: "PATCH",
    OptionsRequest: "OPTIONS",
    HeadRequest: "HEAD",
}
