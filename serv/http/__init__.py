"""HTTP layer for Serv - request/response handling, forms, validation."""

# Re-export from existing modules for backward compatibility
try:
    from .forms import FileUpload, Form
    from .requests import (
        DeleteRequest,
        GetRequest,
        PatchRequest,
        PostRequest,
        PutRequest,
    )
    from .responses import (
        HtmlResponse as HTMLResponse,  # Alias for backward compatibility
    )
    from .responses import (
        JsonResponse as JSONResponse,  # Alias for backward compatibility
    )
    from .responses import (
        RedirectResponse,
        Response,
        ResponseBuilder,
        TextResponse,
    )

    __all__ = [
        "GetRequest",
        "PostRequest",
        "PutRequest",
        "DeleteRequest",
        "PatchRequest",
        "JSONResponse",
        "HTMLResponse",
        "TextResponse",
        "RedirectResponse",
        "Response",
        "ResponseBuilder",
        "FileUpload",
        "Form",
    ]
except ImportError:
    # If direct imports fail, will be populated later during refactoring
    __all__ = []
