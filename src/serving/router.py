from dataclasses import dataclass, field
from typing import Any, Callable, Literal, overload

from starlette.routing import Route

from serving.config import ConfigModel

type HTTPMethod = Literal['GET', 'POST', 'PUT', 'DELETE']


@dataclass
class RouteConfig:
    path: str
    method: HTTPMethod = "GET"
    permissions: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, config: dict) -> "RouteConfig":
        return cls(
            path=config["path"],
            method=config.get("method", "GET"),
            permissions=set(config.get("permissions", []))
        )


@dataclass
class RouterConfig(ConfigModel, model_key="routers", is_collection=True):
    entrypoint: str = ""
    prefix: str = ""
    routes: list[RouteConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, config: dict) -> "RouterConfig":
        routes = [
            RouteConfig.from_dict(route)
            for route in config.get("routes", [])
        ]
        return cls(
            entrypoint=config["entrypoint"],
            prefix=config.get("prefix", ""),
            routes=routes,
        )



class Router:
    def __init__(self):
        self.routes = []

    @overload
    def route(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    @overload
    def route(self, path: str, methods: set[HTTPMethod]) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    def route[**P, R](self, path: str, *args, **kwargs) -> Callable[[Callable[P, R]], Callable[P, R]]:
        if len(args) > 1:
            raise ValueError("Too many arguments")

        if len(args) == 1 and "methods" in kwargs:
            raise ValueError("Methods cannot be specified as both an argument and a keyword argument")

        if len(args) == 1:
            methods = args[0]

        elif "methods" in kwargs:
            methods = kwargs["methods"]

        else:
            methods = {"GET"}

        if not isinstance(methods, set) or not all(isinstance(method, str) for method in methods):
            raise ValueError("Methods must be a set of strings")

        # Normalize methods to upper-case and ensure HEAD accompanies GET for convenience
        normalized_methods = {m.upper() for m in methods}
        if "GET" in normalized_methods:
            normalized_methods.add("HEAD")

        def decorator(func: Callable[P, R]) -> Callable[P, R]:
            # Starlette accepts an iterable of method strings; pass a list for consistency
            self.routes.append(Route(path, func, methods=list(normalized_methods)))
            return func

        return decorator
