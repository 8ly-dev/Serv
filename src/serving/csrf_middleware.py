from bevy import Inject, auto_inject, injectable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.status import HTTP_400_BAD_REQUEST

from serving.auth import CredentialProvider


class CSRFMiddleware(BaseHTTPMiddleware):
    @auto_inject
    @injectable
    async def dispatch(
        self,
        request: Request,
        call_next,
        credential_provider: Inject[CredentialProvider],
    ):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            form = await request.form()
            token = form.get("csrf_token")
            if not token or not credential_provider.validate_csrf_token(token):
                return PlainTextResponse(
                    "Invalid CSRF token", status_code=HTTP_400_BAD_REQUEST
                )
        return await call_next(request)
