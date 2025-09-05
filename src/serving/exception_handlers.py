"""Exception handlers for Starlette with themed error pages."""
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Handle HTTP exceptions with themed error pages."""
    serv = request.app.state.serv
    return serv.error_handler.render_error(
        request,
        error_code=exc.status_code,
        error_message=exc.detail or None,
        details=None
    )


async def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle general exceptions as 500 errors with themed error pages."""
    serv = request.app.state.serv
    
    import traceback
    import io
    
    # Format exception details
    details = str(exc)
    
    # Include full traceback in development mode
    if hasattr(serv, 'environment') and serv.environment in ('dev', 'development'):
        # Format the exception with traceback
        tb_str = io.StringIO()
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=tb_str)
        details = tb_str.getvalue()
    
    return serv.error_handler.render_error(
        request,
        error_code=500,
        error_message="Internal Server Error",
        details=details
    )


async def not_found_handler(request: Request, exc: HTTPException) -> Response:
    """Handle 404 errors with themed error pages."""
    serv = request.app.state.serv
    return serv.error_handler.render_error(
        request,
        error_code=404,
        error_message="Not Found",
        details=f"The requested path '{request.url.path}' could not be found."
    )