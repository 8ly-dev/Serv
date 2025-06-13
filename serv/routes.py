"""Legacy route exports for backward compatibility.

All route functionality has been moved to specialized modules.
This module provides re-exports for backward compatibility.
"""

# Import Route class and decorators from routing modules
from serv.http.forms import FileUpload, Form

# Import HTTP-related classes from http modules (for backward compatibility)
from serv.http.requests import (
    DeleteRequest,
    GetRequest,
    HeadRequest,
    MethodMapping,
    OptionsRequest,
    PatchRequest,
    PostRequest,
    PutRequest,
)
from serv.http.responses import (
    FileResponse,
    HtmlResponse,
    Jinja2Response,
    JsonResponse,
    RedirectResponse,
    Response,
    ResponseBuilder,
    ServerSentEventsResponse,
    StreamingResponse,
    TextResponse,
)
from serv.routing.decorators import handle
from serv.routing.handlers import Route

# Re-export for backward compatibility
__all__ = [
    "Route",
    "handle",
    # HTTP requests
    "GetRequest",
    "PostRequest",
    "PutRequest",
    "DeleteRequest",
    "PatchRequest",
    "OptionsRequest",
    "HeadRequest",
    "MethodMapping",
    # HTTP responses
    "ResponseBuilder",
    "Response",
    "JsonResponse",
    "TextResponse",
    "HtmlResponse",
    "FileResponse",
    "StreamingResponse",
    "ServerSentEventsResponse",
    "RedirectResponse",
    "Jinja2Response",
    # Forms
    "Form",
    "FileUpload",
]
