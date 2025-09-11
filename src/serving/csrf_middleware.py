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
            # Avoid consuming the request body here to prevent stream reuse issues.
            # If a CSRF token is provided via header, validate it preemptively.
            header_token = request.headers.get("x-csrf-token")
            if header_token is not None:
                if not credential_provider.validate_csrf_token(header_token):
                    return PlainTextResponse(
                        "Invalid CSRF token", status_code=HTTP_400_BAD_REQUEST
                    )
            # Otherwise, allow downstream handlers (e.g., Form.from_request) to validate
            # CSRF from the form body without the stream being consumed twice.
        return await call_next(request)
