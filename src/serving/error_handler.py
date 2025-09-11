"""Error handler with theming support."""
from pathlib import Path

from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates


class ErrorHandler:
    """Handles errors with themed templates."""
    
    def __init__(self, theming_config=None, templates=None):
        """Initialize error handler with theming configuration.
        
        Args:
            theming_config: ThemingConfig object with error template settings
            templates: Jinja2Templates instance for custom templates
        """
        self.theming_config = theming_config
        self.custom_templates = templates
        
        # Setup fallback templates
        fallback_dir = Path(__file__).parent / "templates"
        self.fallback_templates = Jinja2Templates(directory=str(fallback_dir))
    
    def render_error(self, request, error_code: int, error_message: str = None, details: str = None) -> HTMLResponse:
        """Render an error page using the appropriate template.
        
        Args:
            request: The Starlette request object
            error_code: HTTP error code
            error_message: Optional custom error message
            details: Optional technical details
        
        Returns:
            HTMLResponse with rendered error page
        """
        # Default error messages if not provided
        if error_message is None:
            error_message = self._get_default_message(error_code)
        
        context = {
            "request": request,
            "error_code": error_code,
            "error_message": error_message,
            "details": details,
        }
        
        # Try to use custom template if configured
        if self.theming_config and self.custom_templates:
            template_path = None
            
            # Check for specific error code template
            if self.theming_config.error_templates:
                template_path = self.theming_config.error_templates.get(str(error_code))
            
            # Fall back to default error template if configured
            if not template_path and self.theming_config.default_error_template:
                template_path = self.theming_config.default_error_template
            
            if template_path:
                try:
                    return self.custom_templates.TemplateResponse(
                        request=request,
                        name=template_path,
                        context=context,
                        status_code=error_code,
                    )
                except Exception:
                    # If custom template fails, fall back to built-in
                    pass
        
        # Use fallback template
        return self.fallback_templates.TemplateResponse(
            request=request,
            name="error.html",
            context=context,
            status_code=error_code,
        )
    
    def _get_default_message(self, error_code: int) -> str:
        """Get default error message for a given error code."""
        messages = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            408: "Request Timeout",
            409: "Conflict",
            410: "Gone",
            413: "Payload Too Large",
            414: "URI Too Long",
            415: "Unsupported Media Type",
            418: "I'm a teapot",
            422: "Unprocessable Entity",
            429: "Too Many Requests",
            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout",
            505: "HTTP Version Not Supported",
        }
        return messages.get(error_code, "Error")
