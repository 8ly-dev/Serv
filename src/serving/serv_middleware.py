from asyncio import CancelledError, get_running_loop
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from serving.response import ServResponse

if TYPE_CHECKING:
    from serving.serv import Serv


class ServMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, serv: "Serv"):
        super().__init__(app)
        self.serv = serv

    async def dispatch(self, request, call_next):
        with self.serv.registry, self.serv.container.branch() as container:
            container.add(Request, request)
            container.add(
                _response := ServResponse()
            )

            _response.running_coroutine = get_running_loop().create_task(call_next(request))
            try:
                response = await _response.running_coroutine
            except CancelledError:
                if _response.response_override is None:
                    raise

                return _response.response_override
            else:
                if _response.response_override is not None:
                    return _response.response_override

            response.headers.update(_response.headers)
            if _response.status_code is not None:
                response.status_code = _response.status_code

            return response






