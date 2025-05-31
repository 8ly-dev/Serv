from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from bevy import dependency

import serv.routing as r
from serv.extensions import Listener, on

if TYPE_CHECKING:
    from serv.extensions.importer import Importer
    from serv.extensions.loader import ExtensionSpec, RouteConfig, RouterConfig


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
            handler = self._get_route_handler(route)
            
            # Check if this is a WebSocket route
            if route.get("websocket", False):
                # Add as WebSocket route
                router.add_websocket(
                    route["path"], 
                    handler, 
                    settings=route.get("config", {})
                )
            else:
                # Add as regular HTTP route
                args = [route["path"], handler]
                if methods := route.get("methods"):
                    args.append(methods)
                router.add_route(*args, settings=route.get("config", {}))

        if self._mount_path:
            main_router.mount(self._mount_path, router)
        else:
            main_router.add_router(router)

    def _get_route_handler(self, route: "RouteConfig") -> Any:
        print("Getting route: ", route)

        handler_str = route["handler"]

        # Validate that handler is a string in the expected format
        if not isinstance(handler_str, str):
            raise ValueError(
                f"Route handler must be a string in format 'module:class', but got {type(handler_str).__name__}: {repr(handler_str)}"
            )

        if ":" not in handler_str:
            raise ValueError(
                f"Route handler must be in format 'module:class', but got: {repr(handler_str)}"
            )

        module, handler = handler_str.split(":")
        module = self._importer.load_module(module)
        return getattr(module, handler)


class RouterExtension(Listener):
    def __init__(self, *, extension_spec: "ExtensionSpec", stand_alone: bool = False):
        super().__init__(extension_spec=extension_spec, stand_alone=stand_alone)
        self._routers: dict[str, RouterBuilder] = dict(
            self._setup_routers(extension_spec.routers)
        )

    def _setup_routers(
        self, routers: "list[RouterConfig]"
    ) -> Generator[tuple[str, RouterBuilder]]:
        """Set up routers based on the extension configuration."""
        for router_config in routers:
            yield router_config["name"], self._build_router(router_config)

    def _build_router(self, router_config: "RouterConfig") -> RouterBuilder:
        """Build a router from the given configuration."""
        router = RouterBuilder(
            router_config.get("mount"),
            router_config.get("config", {}),
            self._build_routes(router_config["routes"]),
            self.__extension_spec__.importer,
        )
        return router

    def _build_routes(self, route_configs: "list[RouteConfig]") -> "list[RouteConfig]":
        """Build routes from the given configuration."""
        return route_configs

    @on("app.request.begin")
    async def setup_routes(self, main_router: "r.Router" = dependency()) -> None:
        for router_builder in self._routers.values():
            router_builder.build(main_router)

    @on("app.websocket.begin")
    async def setup_websocket_routes(self, main_router: "r.Router" = dependency()) -> None:
        """Set up routes for WebSocket connections.
        
        WebSocket connections use a fresh router instance, so we need to register
        routes during the websocket.begin event as well.
        """
        for router_builder in self._routers.values():
            router_builder.build(main_router)
