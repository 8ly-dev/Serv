from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from bevy import Inject, injectable

import serv.routing as r
from serv.additional_context import ExceptionContext
from serv.auth.declarative import AuthRule, DeclarativeAuthProcessor
from serv.extensions import Listener, on
from serv.http import Request

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
        auth_rule: AuthRule | None = None,
    ):
        self._mount_path = mount_path
        self._settings = settings
        self._routes = routes
        self._importer = importer
        self._auth_rule = auth_rule

    def build(self, main_router: "r.Router", request: Request | None = None):
        # Evaluate router-level auth - if it fails, don't mount the router (results in 404)
        if self._auth_rule and request:
            user_context = getattr(request, "user_context", None)
            is_allowed, reason = DeclarativeAuthProcessor.evaluate_auth_rule(
                self._auth_rule, user_context
            )
            if not is_allowed:
                # Router auth failed - don't mount, resulting in 404
                return

        router = r.Router(self._settings)
        for route in self._routes:
            handler = self._get_route_handler(route)

            # Merge router and route auth rules for route settings
            route_auth_rule = DeclarativeAuthProcessor.parse_auth_config(route.get("auth"))
            merged_auth_rule = DeclarativeAuthProcessor.merge_router_and_route_auth(
                self._auth_rule, route_auth_rule
            )

            # Add auth rule to route settings
            route_settings = route.get("config", {}).copy()
            if merged_auth_rule:
                route_settings["auth_rule"] = merged_auth_rule

            # Check if this is a WebSocket route
            if route.get("websocket", False):
                # Add as WebSocket route
                router.add_websocket(route["path"], handler, settings=route_settings)
            else:
                # Add as regular HTTP route
                args = [route["path"], handler]
                if methods := route.get("methods"):
                    args.append(methods)
                router.add_route(*args, settings=route_settings)

        if self._mount_path:
            main_router.mount(self._mount_path, router)
        else:
            main_router.add_router(router)

    def _get_route_handler(self, route: "RouteConfig") -> Any:

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
        with ExceptionContext().apply_note(
            f" - Attempting to import module {module}:{handler} with route config {route}"
        ):
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
        # Parse router-level auth configuration
        router_auth_rule = DeclarativeAuthProcessor.parse_auth_config(
            router_config.get("auth")
        )
        
        router = RouterBuilder(
            router_config.get("mount"),
            router_config.get("config", {}),
            self._build_routes(router_config["routes"]),
            self.__extension_spec__.importer,
            router_auth_rule,
        )
        return router

    def _build_routes(self, route_configs: "list[RouteConfig]") -> "list[RouteConfig]":
        """Build routes from the given configuration."""
        return route_configs

    @on("app.request.begin")
    @injectable
    async def setup_routes(self, main_router: Inject["r.Router"], request: Inject[Request]) -> None:
        for router_builder in self._routers.values():
            router_builder.build(main_router, request)

    @on("app.websocket.begin")
    @injectable
    async def setup_websocket_routes(self, main_router: Inject["r.Router"], request: Inject[Request]) -> None:
        """Set up routes for WebSocket connections.

        WebSocket connections use a fresh router instance, so we need to register
        routes during the websocket.begin event as well.
        """
        for router_builder in self._routers.values():
            router_builder.build(main_router, request)
