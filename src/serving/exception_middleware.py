"""Exception handling middleware with themed error pages."""
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ExceptionMiddleware(BaseHTTPMiddleware):
    """Middleware that handles exceptions and renders themed error pages."""
    
    def __init__(self, app, serv):
        super().__init__(app)
        self.serv = serv
        
    async def dispatch(self, request: Request, call_next) -> Response:
        """Handle exceptions and render appropriate error pages."""
        try:
            response = await call_next(request)
            
            # Handle 404 responses
            if response.status_code == 404:
                # Only show path details in development mode
                details = None
                if hasattr(self.serv, 'environment') and self.serv.environment in ('dev', 'development'):
                    details = f"The requested path '{request.url.path}' could not be found."
                
                return self.serv.error_handler.render_error(
                    request,
                    error_code=404,
                    error_message="Not Found",
                    details=details
                )
            
            return response
            
        except HTTPException as exc:
            # Handle HTTP exceptions with themed error pages
            return self.serv.error_handler.render_error(
                request,
                error_code=exc.status_code,
                error_message=exc.detail or None,
                details=None
            )
            
        except Exception as exc:
            # Handle general exceptions as 500 errors
            # Only show details in development mode
            details = None
            if hasattr(self.serv, 'environment') and self.serv.environment in ('dev', 'development'):
                import traceback
                import io
                
                # Format the exception with traceback
                tb_str = io.StringIO()
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=tb_str)
                details = tb_str.getvalue()
            
            return self.serv.error_handler.render_error(
                request,
                error_code=500,
                error_message="Internal Server Error",
                details=details
            )