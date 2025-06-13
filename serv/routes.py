"""Legacy route exports for backward compatibility.

All route functionality has been moved to specialized modules.
This module provides re-exports for backward compatibility.
"""

# Import Route class and decorators from routing modules
from serv.routing.decorators import handle
from serv.routing.handlers import Route

# Import HTTP-related classes from http modules (for backward compatibility)
from serv.http.requests import (
    GetRequest,
    PostRequest,
    PutRequest,
    DeleteRequest,
    PatchRequest,
    OptionsRequest,
    HeadRequest,
    MethodMapping,
)
from serv.http.responses import (
    ResponseBuilder,
    Response,
    JsonResponse,
    TextResponse,
    HtmlResponse,
    FileResponse,
    StreamingResponse,
    ServerSentEventsResponse,
    RedirectResponse,
    Jinja2Response,
)
from serv.http.forms import Form, FileUpload

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
