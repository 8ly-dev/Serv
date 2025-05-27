from typing import Annotated, Any

from serv.routes import GetRequest, Jinja2Response, Route


class HomeRoute(Route):
    async def on_get(
        self, request: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        return "home.html", {"request": request}


class AboutRoute(Route):
    async def on_get(
        self, request: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        return "about.html", {"request": request}


class DashboardRoute(Route):
    async def on_get(
        self, request: GetRequest
    ) -> Annotated[tuple[str, dict[str, Any]], Jinja2Response]:
        return "dashboard.html", {"request": request}
