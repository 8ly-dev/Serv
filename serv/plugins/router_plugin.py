from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from bevy import dependency

import serv.routing as r
from serv.plugins import Plugin

if TYPE_CHECKING:
    from serv.plugins.importer import Importer
    from serv.plugins.loader import PluginSpec, RouteConfig, RouterConfig


class RouterBuilder:
    def __init__(
        self,
        mount_path: str | None,
        settings: dict[str, Any],
        routes: "list[RouteConfig]",
        importer: "Importer",
    ):
        self._mount_path = mount_path
        self._settings = settings
        self._routes = routes
        self._importer = importer

    def build(self, main_router: "r.Router"):
        router = r.Router(self._settings)
        for route in self._routes:
            args = [route["path"], self._get_route_handler(route)]
            if methods := route.get("methods"):
                args.append(methods)

            router.add_route(*args, settings=route.get("config", {}))

        if self._mount_path:
            main_router.mount(self._mount_path, router)
        else:
            main_router.add_router(router)

    def _get_route_handler(self, route: "RouteConfig") -> Any:
        print("Getting route: ", route)
        module, handler = route["handler"].split(":")
        module = self._importer.load_module(module)
        return getattr(module, handler)


class RouterPlugin(Plugin):
    def __init__(self, *, plugin_spec: "PluginSpec", stand_alone: bool = False):
        super().__init__(plugin_spec=plugin_spec, stand_alone=stand_alone)
        self._routers: dict[str, RouterBuilder] = dict(
            self._setup_routers(plugin_spec.routers)
        )

    def _setup_routers(
        self, routers: "list[RouterConfig]"
    ) -> Generator[tuple[str, RouterBuilder]]:
        """Set up routers based on the plugin configuration."""
        for router_config in routers:
            yield router_config["name"], self._build_router(router_config)

    def _build_router(self, router_config: "RouterConfig") -> RouterBuilder:
        """Build a router from the given configuration."""
        router = RouterBuilder(
            router_config.get("mount"),
            router_config.get("config", {}),
            self._build_routes(router_config["routes"]),
            self.__plugin_spec__.importer,
        )
        return router

    def _build_routes(self, route_configs: "list[RouteConfig]") -> "list[RouteConfig]":
        """Build routes from the given configuration."""
        return route_configs

    async def on_app_request_begin(
        self, main_router: "r.Router" = dependency()
    ) -> None:
        for router_builder in self._routers.values():
            router_builder.build(main_router)
