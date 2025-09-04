from asyncio import Task
from dataclasses import dataclass, field
from enum import IntEnum

from bevy import get_container
from starlette.responses import RedirectResponse, Response

from serving.utilities import ensure_request_lifecycle


class RequestLifecycleNotStarted(Exception):
    pass


class Status(IntEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    MISDIRECTED_REQUEST = 300
    MOVED_PERMANENTLY = 301
    FOUND = 302
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    USE_PROXY = 305
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    EXPIRED = 410
    PRECONDITION_FAILED = 412
    TEAPOT = 418
    UNPROCESSABLE_ENTITY = 422
    TOO_EARLY = 425
    UPGRADE_REQUIRED = 426
    PRECONDITION_REQUIRED = 428
    TOO_MANY_REQUESTS = 429
    REQUEST_HEADER_FIELDS_TOO_LARGE = 431
    RETRY_WITH = 449
    BLOCKED = 450
    UNAVAILABLE = 451
    INTERNAL_SERVER_ERROR = 500


@dataclass
class ServResponse:
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    running_coroutine: Task | None = None
    response_override: Response | None = None

    def cancel(self, msg: str = ""):
        if self.running_coroutine is not None:
            self.running_coroutine.cancel(msg)
            self.running_coroutine = None


@ensure_request_lifecycle
def set_header(name: str, value: str):
    response = get_container().get(ServResponse)
    response.headers[name] = value


@ensure_request_lifecycle
def set_status_code(status_code: int | Status):
    response = get_container().get(ServResponse)
    match status_code:
        case int():
            response.status_code = status_code
        case Status():
            response.status_code = status_code.value
        case _:
            raise ValueError(f"Invalid status code: {status_code}")


@ensure_request_lifecycle
def set_cookie(name: str, value: str):
    response = get_container().get(ServResponse)
    response.headers['Set-Cookie'] = f"{name}={value}"


@ensure_request_lifecycle
def delete_cookie(name: str):
    response = get_container().get(ServResponse)
    response.headers['Set-Cookie'] = f"{name}=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT"


@ensure_request_lifecycle
def redirect(url: str, status_code: int | Status = Status.TEMPORARY_REDIRECT):
    match status_code:
        case int():
            pass
        case Status():
            status_code = status_code.value
        case _:
            raise ValueError(f"Invalid status code: {status_code}")

    response = get_container().get(ServResponse)
    response.response_override = RedirectResponse(url, status_code=status_code)
    response.cancel(f"{Status(status_code)} Redirect to {url}")

