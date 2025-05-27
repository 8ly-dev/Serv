from bevy import dependency

from serv.extensions import Extension
from serv.responses import ResponseBuilder
from serv.routing import Router


class TestExtensionExtension(Extension):
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        router.add_route("/test-route", self._handler, methods=["GET"])

    async def _handler(self, response: ResponseBuilder = dependency()):
        response.content_type("text/plain")
        response.body("Hello from test plugin!")
