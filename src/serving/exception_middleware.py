"""Exception handling middleware with themed error pages."""
import logging
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.routing import Mount
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
                # In development, if static is configured to serve assets, log missing static file details
                try:
                    env = getattr(self.serv, 'environment', 'prod')
                    is_dev = env in ('dev', 'development')
                    if is_dev:
                        from serving.config import Config  # local import to avoid cycles
                        config = self.serv.container.get(Config)
                        static_cfg = config.get('static') or {}
                        mount = static_cfg.get('mount', '/static') or '/static'
                        directory = static_cfg.get('directory', 'static')
                        serve_opt = static_cfg.get('serve')
                        serve_assets = serve_opt if serve_opt is not None else True  # dev default True

                        if mount and request.url.path.startswith(mount + '/'):
                            # Detect whether a static mount exists in the app routes
                            is_mounted = any(
                                isinstance(r, Mount) and r.path == mount for r in getattr(self.serv.app, 'routes', [])
                            )
                            base_dir = self.serv.get_config_path(self.serv.working_directory, self.serv.environment).parent
                            dir_path = Path(directory)
                            if not dir_path.is_absolute():
                                dir_path = base_dir / dir_path

                            if not is_mounted:
                                logging.getLogger('serving.static').warning(
                                    "Static route not mounted for request under mount=%s (dir=%s). Check 'static.mount'/'static.serve' settings.",
                                    mount,
                                    str(dir_path),
                                )
                            elif serve_assets:
                                rel = request.url.path[len(mount) + 1 :]  # strip mount and leading slash
                                resolved = dir_path / rel
                                if not resolved.exists():
                                    logging.getLogger('serving.static').warning(
                                        "Static asset not found: url=%s resolved=%s (mount=%s, dir=%s)",
                                        request.url.path,
                                        str(resolved),
                                        mount,
                                        str(dir_path),
                                    )
                except Exception:
                    # Do not allow logging to interfere with error rendering
                    pass
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
            # Log server error HTTPExceptions with stacktraces in all environments
            try:
                status = int(getattr(exc, 'status_code', 500))
            except Exception:
                status = 500
            if status >= 500:
                logging.getLogger('serving.app').error(
                    "HTTPException %s for %s: %s", status, request.url.path, exc.detail, exc_info=True
                )
            return self.serv.error_handler.render_error(
                request,
                error_code=exc.status_code,
                error_message=exc.detail or None,
                details=None
            )
            
        except Exception as exc:
            # Handle general exceptions as 500 errors; log stacktraces in all environments
            logging.getLogger('serving.app').error(
                "Unhandled exception for %s", request.url.path, exc_info=True
            )
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
