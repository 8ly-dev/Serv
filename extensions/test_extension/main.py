from bevy import Inject

from serv.extensions import Extension
from serv.responses import ResponseBuilder
from serv.routing import Router


class TestExtensionExtension(Extension):
    async def on_app_request_begin(self, router: Inject[Router]) -> None:
        router.add_route("/test-route", self._handler, methods=["GET"])

    async def _handler(self, response: Inject[ResponseBuilder]):
        response.content_type("text/plain")
        response.body("Hello from test plugin!")
