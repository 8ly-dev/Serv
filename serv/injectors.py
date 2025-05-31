from typing import Annotated, Any, get_args, get_origin

from bevy.containers import Container
from bevy.hooks import hooks
from tramp.optionals import Optional

from serv.requests import Request


class _Marker:
    __match_args__ = ("name", "default")


class Header(_Marker):
    def __init__(self, name: str, default: str | None = None):
        self.name = name
        self.default = default

    def __repr__(self):
        return f"<Inject:Header({self.name!r}, default={self.default!r})>"


class Cookie(_Marker):
    def __init__(self, name: str, default: str | None = None):
        self.name = name
        self.default = default

    def __repr__(self):
        return f"<Inject:Cookie({self.name!r}, default={self.default!r})>"


class Query(_Marker):
    def __init__(self, name: str, default: str | None = None):
        self.name = name
        self.default = default

    def __repr__(self):
        return f"<Inject:Query({self.name!r}, default={self.default!r})>"


@hooks.CREATE_INSTANCE
def inject_request_object(container: Container, annotation: Any) -> Optional[Any]:
    origin = get_origin(annotation)
    if origin is Annotated:
        annotation_type, marker = get_args(annotation)
        request = container.get(Request)
        match marker:
            case Header(name, default):
                return Optional.Some(request.headers.get(name, default))
            case Cookie(name, default):
                return Optional.Some(request.cookies.get(name, default))
            case Query(name, default):
                return Optional.Some(request.query_params.get(name, default))

    return Optional.Nothing()


@hooks.CREATE_INSTANCE
def inject_websocket_object(container: Container, annotation: Any) -> Optional[Any]:
    """Inject WebSocket instances with proper frame type configuration.

    Handles both plain WebSocket injection and Annotated[WebSocket, FrameType.X] patterns.
    """
    from serv.websocket import WebSocket, FrameType

    # Handle plain WebSocket type
    if isinistance(annotation, type) and issubclass(annotation, WebSocket):
        if websocket := container.get_optional(annotation):
            return websocket

    # Handle Annotated[WebSocket, FrameType.X] pattern
    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if len(args) >= 2 and isinstance(args[0], type) and issubclass(args[0], WebSocket):
            websocket_opt = container.get(WebSocket)
            if websocket_opt:
                websocket = websocket_opt.unwrap()

                # Check for FrameType annotation and update if needed
                for annotation_arg in args[1:]:
                    if isinstance(annotation_arg, FrameType):
                        websocket.frame_type = annotation_arg
                        break

                return Optional.Some(websocket)

    return Optional.Nothing()
