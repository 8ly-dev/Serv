"""Route handling for Serv applications."""

import sys
from collections import defaultdict
from contextlib import suppress
from functools import cached_property
from inspect import signature
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin

from bevy import Inject, injectable
from bevy.containers import Container

import serv.extensions.loader as pl
from serv.exceptions import HTTPBadRequestException, HTTPMethodNotAllowedException
from serv.extensions import Listener
from serv.protocols import EventEmitterProtocol

# Re-export commonly used classes for backward compatibility
from ..http.request_types import (  # noqa: F401
    DeleteRequest,
    GetRequest,
    HeadRequest,
    MethodMapping,
    OptionsRequest,
    PatchRequest,
    PostRequest,
    PutRequest,
)
from ..http.requests import Request
from ..http.response_types import Jinja2Response  # noqa: F401
from ..http.response_utils import BaseResponse as Response
from ..http.response_utils import (  # noqa: F401
    FileResponse,
    HtmlResponse,
    JsonResponse,
    TextResponse,
)
from ..http.responses import ResponseBuilder
from ..utils.form_utils import Form
from ..utils.type_utils import get_safe_type_hints
from ..utils.utils import is_subclass_of
from .handler_utils import HandlerProcessor, ResponseProcessor
from .route_decorators import handle  # noqa: F401


class Route:
    """Base class for creating HTTP route handlers in Serv applications."""

    __method_handlers__: dict[str, list[dict]]
    __error_handlers__: dict[type[Exception], str]
    __form_handlers__: dict[str, dict[type[Form], list[str]]]
    __annotated_response_wrappers__: dict[str, type[Response]]

    def __init_subclass__(cls) -> None:
        cls._initialize_class_attributes()
        cls._discover_handlers()

    @classmethod
    def _initialize_class_attributes(cls) -> None:
        """Initialize class-level handler registries."""
        cls.__method_handlers__ = defaultdict(list)
        cls.__error_handlers__ = {}
        cls.__form_handlers__ = defaultdict(lambda: defaultdict(list))
        cls.__annotated_response_wrappers__ = {}

    @classmethod
    def _discover_handlers(cls) -> None:
        """Discover and register all handler methods in the class."""
        for method_name in dir(cls):
            if method_name.startswith("_"):
                continue

            method_callable = getattr(cls, method_name)
            if not callable(method_callable):
                continue

            method_signature = signature(method_callable)
            method_parameters = list(method_signature.parameters.values())

            if not method_parameters:
                continue

            # Process this method for various handler types
            cls._register_response_wrapper(method_name, method_callable)
            cls._register_method_handler(method_name, method_callable, method_signature)
            cls._register_form_and_error_handlers(method_name, method_parameters)

    @classmethod
    def _register_response_wrapper(
        cls, method_name: str, method_callable: callable
    ) -> None:
        """Register annotated response wrapper for a method."""
        try:
            handler_type_hints = get_safe_type_hints(
                method_callable, include_extras=True
            )
            return_annotation = handler_type_hints.get("return")
        except Exception:
            return_annotation = None

        if return_annotation and get_origin(return_annotation) is Annotated:
            annotation_args = get_args(return_annotation)
            if len(annotation_args) == 2 and is_subclass_of(
                annotation_args[1], Response
            ):
                response_wrapper_class = annotation_args[1]
                cls.__annotated_response_wrappers__[method_name] = (
                    response_wrapper_class
                )

    @classmethod
    def _register_method_handler(
        cls, method_name: str, method_callable: callable, method_signature
    ) -> None:
        """Register HTTP method handlers based on decorators."""
        if hasattr(method_callable, "__handle_methods__"):
            for http_method in method_callable.__handle_methods__:
                if http_method == "FORM":
                    continue
                cls.__method_handlers__[http_method].append(
                    {
                        "name": method_name,
                        "method": method_callable,
                        "signature": method_signature,
                    }
                )

    @classmethod
    def _register_form_and_error_handlers(
        cls, method_name: str, method_parameters: list
    ) -> None:
        """Register form and error handlers based on parameter annotations."""
        if len(method_parameters) <= 1:
            return

        # Check the second parameter (after 'self') for Form or Exception types
        second_param_annotation = method_parameters[1].annotation

        if is_subclass_of(second_param_annotation, Form):
            form_class = second_param_annotation
            http_method = form_class.__form_method__
            cls.__form_handlers__[http_method][form_class].append(method_name)

        elif is_subclass_of(second_param_annotation, Exception):
            exception_class = second_param_annotation
            cls.__error_handlers__[exception_class] = method_name

    @injectable
    async def __call__(
        self,
        request: Inject[Request],
        container: Inject[Container],
        response_builder: Inject[ResponseBuilder],
        /,
        **path_params,
    ):
        match await self._handle_request(request, container, path_params):
            case Response(status_code, headers) as result:
                response_builder.set_status(status_code)
                for header, value in headers.items():
                    response_builder.add_header(header, value)
                response_builder.body(container.call(result.render))

            case result:
                raise TypeError(f"Expected Response, got {type(result)}")

    @cached_property
    def extension(self) -> Listener | None:
        """Get the extension spec for this route's module."""
        with suppress(Exception):
            return pl.find_extension_spec(Path(sys.modules[self.__module__].__file__))
        return None

    @injectable
    async def emit(
        self,
        event: str,
        emitter: Inject[EventEmitterProtocol],
        /,
        *,
        container: Inject[Container],
        **kwargs: Any,
    ):
        return await emitter.emit(event, container=container, **kwargs)

    async def _try_form_handler(
        self, request: Request, container: Container, path_params: dict
    ):
        """Try to find and prepare a form handler."""
        method = request.method
        if not self.__form_handlers__.get(method):
            return None

        form_data = await request.form()

        for form_type, form_handler_names in self.__form_handlers__[method].items():
            if not form_type.matches_form_data(form_data):
                continue

            for handler_name in form_handler_names:
                try:
                    parsed_form = await request.form(form_type, data=form_data)
                    handler = getattr(self, handler_name)
                    handler_info = {"name": handler_name, "method": handler}
                    return handler, handler_info, [parsed_form]
                except Exception as e:
                    error_response = await container.call(
                        self._error_handler, e, path_params
                    )
                    return error_response, None, None
        return None

    async def _try_method_handler(
        self, request: Request, container: Container, path_params: dict
    ):
        """Try to find and prepare a method handler using the HandlerProcessor."""
        processor = HandlerProcessor(self)

        method = request.method
        if method not in self.__method_handlers__:
            raise HTTPMethodNotAllowedException(
                f"{type(self).__name__} does not support {method}.",
                list(self.__method_handlers__.keys() | self.__form_handlers__.keys()),
            )

        handlers = self.__method_handlers__[method]
        has_form_handlers = bool(self.__form_handlers__.get(method))

        if len(handlers) == 1:
            return await processor.try_single_handler(
                handlers[0], request, path_params, container, has_form_handlers
            )

        return await processor.try_multiple_handlers(
            handlers, request, path_params, container, has_form_handlers
        )

    async def _handle_request(
        self, request: Request, container: Container, path_params: dict
    ) -> Response:
        """Handle an incoming request by finding and calling the appropriate handler."""
        response_processor = ResponseProcessor(self)

        # Try form handler first
        form_result = await self._try_form_handler(request, container, path_params)

        if form_result and len(form_result) == 3:
            handler, handler_info, args = form_result
            try:
                output = await self._call_handler(handler, {}, args, container)
                response = await response_processor.create_response(
                    output, handler_info, request
                )
                response.set_created_by(self.extension)
                return response
            except Exception as e:
                return await self._handle_error(e, container)

        if form_result and len(form_result) == 2:
            # Error response from form handler
            error_response, _ = form_result
            return error_response

        # Try method handler
        try:
            method_result = await self._try_method_handler(
                request, container, path_params
            )
            output = await self._call_handler(
                method_result.handler, method_result.kwargs, [], container
            )
            response = await response_processor.create_response(
                output, method_result.handler_info, request
            )
            response.set_created_by(self.extension)
            return response

        except (HTTPBadRequestException, HTTPMethodNotAllowedException) as e:
            return await self._handle_error(e, container)
        except Exception as e:
            return await self._handle_error(e, container)

    async def _call_handler(
        self, handler: Any, kwargs: dict, args: list, container: Container
    ) -> Any:
        """Call the handler with the appropriate parameters."""
        match (bool(kwargs), bool(args)):
            case (True, _):
                return await container.call(handler, self, **kwargs)
            case (False, True):
                return await handler(*args)
            case (False, False):
                return await container.call(handler, self)
            case _:
                raise ValueError("Invalid handler call parameters")

    async def _handle_error(self, error: Exception, container: Container) -> Response:
        """Handle an error by calling the appropriate error handler."""
        return await container.call(self._error_handler, error, container)

    async def _error_handler(
        self, exception: Exception, container: Container
    ) -> Response:
        """Handle errors by checking for custom error handlers."""
        for error_type, handler_name in self.__error_handlers__.items():
            if isinstance(exception, error_type):
                handler = getattr(self, handler_name)
                return await container.call(handler, exception)

        # No custom handler found - re-raise to let App handle it
        raise exception
