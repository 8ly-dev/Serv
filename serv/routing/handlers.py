"""Route handler base class and handler management for Serv routing.

This module provides the Route base class and related utilities for creating
HTTP route handlers with automatic method discovery, parameter injection,
response type inference, and error handling.
"""

import json
import sys
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import date, datetime
from functools import wraps
from inspect import get_annotations, signature
from pathlib import Path
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from bevy import Inject, injectable
from bevy.containers import Container

import serv.extensions.loader as pl
from serv.exceptions import HTTPMethodNotAllowedException
from serv.extensions import Listener
from serv.injectors import Cookie, Header, Query
from serv.protocols import (
    AppContextProtocol,
    EventEmitterProtocol,
)
from serv.requests import Request
from serv.http.requests import (
    GetRequest,
    PostRequest,
    PutRequest,
    DeleteRequest,
    PatchRequest,
    OptionsRequest,
    HeadRequest,
    MethodMapping,
)
from serv.http.responses import (
    ResponseBuilder,
    Response,
    JsonResponse,
    TextResponse,
    HtmlResponse,
    FileResponse,
    StreamingResponse,
    ServerSentEventsResponse,
    RedirectResponse,
    Jinja2Response,
)
from serv.http.forms import (
    Form,
    is_optional,
    normalized_origin,
    string_value_type_validators,
    _is_valid_type,
    _datetime_validator,
    _date_validator,
)
from serv.routing.decorators import handle


class Route:
    """Base class for creating HTTP route handlers in Serv applications.

    Route classes provide a structured way to handle HTTP requests by defining
    methods that correspond to HTTP methods (GET, POST, etc.) and form handlers.
    They support automatic request parsing, response type annotations, error
    handling, and dependency injection.

    The Route class automatically discovers handler methods based on their
    naming patterns and signatures:
    - Methods named `handle_<method>` become HTTP method handlers (e.g., `handle_get`, `handle_post`)
    - Methods with Form subclass parameters become form handlers
    - Methods with Exception parameters become error handlers
    - Return type annotations determine response wrapper classes
    - Handler selection is based on signature matching with request data

    Examples:
        Basic route with HTTP method handlers:

        ```python
        from serv.routes import Route
        from serv.responses import JsonResponse, TextResponse
        from serv.injectors import Query, Header
        from typing import Annotated

        class UserRoute(Route):
            async def handle_get(self, user_id: Annotated[str, Query("id")]) -> Annotated[dict, JsonResponse]:
                return {"id": user_id, "name": "John Doe"}

            async def handle_post(self, data: dict) -> Annotated[str, TextResponse]:
                # Create user logic here
                return "User created successfully"
        ```

        Route with multiple GET handlers based on parameters:

        ```python
        class ProductRoute(Route):
            # Handler for requests with 'id' query parameter
            async def handle_get(self, product_id: Annotated[str, Query("id")]) -> Annotated[dict, JsonResponse]:
                return {"id": product_id, "name": "Product Name"}

            # Handler for requests with 'category' query parameter
            async def handle_get_by_category(self, category: Annotated[str, Query("category")]) -> Annotated[list, JsonResponse]:
                return [{"id": 1, "name": "Product 1"}, {"id": 2, "name": "Product 2"}]

            # Handler for requests with no specific parameters (fallback)
            async def handle_get_all(self) -> Annotated[list, JsonResponse]:
                return [{"id": 1, "name": "All Products"}]
        ```

        Route with form handling:

        ```python
        from serv.routes import Route, Form
        from serv.responses import HtmlResponse
        from typing import Annotated

        class ContactForm(Form):
            name: str
            email: str
            message: str

        class ContactRoute(Route):
            async def handle_get(self) -> Annotated[str, HtmlResponse]:
                return '''
                <form method="post">
                    <input name="name" placeholder="Name" required>
                    <input name="email" type="email" placeholder="Email" required>
                    <textarea name="message" placeholder="Message" required></textarea>
                    <button type="submit">Send</button>
                </form>
                '''

            async def handle_contact_form(self, form: ContactForm) -> Annotated[str, HtmlResponse]:
                # Process the form submission
                await self.send_email(form.email, form.name, form.message)
                return "<h1>Thank you! Your message has been sent.</h1>"
        ```

        Route with header and cookie injection:

        ```python
        from serv.injectors import Header, Cookie

        class AuthRoute(Route):
            async def handle_get(
                self,
                auth_token: Annotated[str, Header("Authorization")],
                session_id: Annotated[str, Cookie("session_id")]
            ) -> Annotated[dict, JsonResponse]:
                # Validate token and session
                return {"authenticated": True, "user": "john_doe"}
        ```

    Note:
        Route classes are automatically instantiated by the router when a matching
        request is received. Handler methods are selected based on the best match
        between the request data and the method's parameter signature. Methods with
        more specific parameter requirements will be preferred over generic handlers.
    """

    __method_handlers__: dict[str, list[dict]]
    __error_handlers__: dict[type[Exception], str]
    __form_handlers__: dict[str, dict[type[Form], list[str]]]
    __annotated_response_wrappers__: dict[str, type[Response]]

    _extension: "Listener | None"

    def __init_subclass__(cls) -> None:
        cls.__method_handlers__ = defaultdict(list)
        cls.__error_handlers__ = {}
        cls.__form_handlers__ = defaultdict(lambda: defaultdict(list))
        cls.__annotated_response_wrappers__ = {}

        try:
            get_type_hints(cls, include_extras=True)
        except Exception:
            pass

        for name in dir(cls):
            if name.startswith("_"):
                continue

            member = getattr(cls, name)
            if not callable(member):
                continue

            sig = signature(member)
            params = list(sig.parameters.values())

            if not params:
                continue

            # Store response wrapper if annotated (applies to ALL handlers)
            try:
                handler_type_hints = get_type_hints(member, include_extras=True)
                return_annotation = handler_type_hints.get("return")
            except Exception:
                return_annotation = None

            if return_annotation and get_origin(return_annotation) is Annotated:
                args = get_args(return_annotation)
                if (
                    len(args) == 2
                    and isinstance(args[1], type)
                    and issubclass(args[1], Response)
                ):
                    cls.__annotated_response_wrappers__[name] = args[1]

            # Handle decorator-based method detection
            if hasattr(member, "__handle_methods__"):
                for http_method in member.__handle_methods__:
                    if http_method == "FORM":
                        # Special handling for FORM - these will be detected by form parameter analysis
                        continue
                    cls.__method_handlers__[http_method].append(
                        {"name": name, "method": member, "signature": sig}
                    )

            # Handle form handlers and error handlers (existing logic)
            if len(params) > 1:
                second_arg_annotation = params[1].annotation

                if isinstance(second_arg_annotation, type) and issubclass(
                    second_arg_annotation, Form
                ):
                    form_type = second_arg_annotation
                    cls.__form_handlers__[form_type.__form_method__][form_type].append(
                        name
                    )

                elif isinstance(second_arg_annotation, type) and issubclass(
                    second_arg_annotation, Exception
                ):
                    cls.__error_handlers__[second_arg_annotation] = name

    @injectable
    async def __call__(
        self,
        request: Inject[Request],
        container: Inject[Container],
        response_builder: Inject[ResponseBuilder],
        /,
        **path_params,
    ):
        handler_result, handler_info = await self._handle_request(
            request, container, path_params
        )

        if isinstance(handler_result, Response):
            response_builder.set_status(handler_result.status_code)
            for header, value in handler_result.headers.items():
                response_builder.add_header(header, value)
            response_builder.body(container.call(handler_result.render))
        else:
            # This should never happen if _handle_request is working correctly,
            # but provide a detailed error message just in case
            handler_name = (
                handler_info.get("name", "unknown") if handler_info else "unknown"
            )
            handler_display = (
                f"{type(self).__name__}.{handler_name}()"
                if handler_name != "unknown"
                else "unknown"
            )

            error_msg = (
                f"Route __call__ received non-Response object:\n"
                f"  Handler: {handler_display}\n"
                f"  Route: {request.method} '{request.path}'\n"
                f"  Received: {type(handler_result).__name__!r} ({repr(handler_result)[:100]}{'...' if len(repr(handler_result)) > 100 else ''})\n"
                f"  Expected: Response instance\n"
                f"  Note: This suggests an issue in _handle_request method - annotated response wrappers should have been applied"
            )

            raise TypeError(error_msg)

    @property
    def extension(self) -> Listener | None:
        if hasattr(self, "_extension"):
            return self._extension

        try:
            self._extension = pl.find_extension_spec(
                Path(sys.modules[self.__module__].__file__)
            )
        except Exception:
            type(self)._extension = None

        return self._extension

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

    def _analyze_handler_signature(self, handler_sig, request: Request) -> dict:
        """Analyze a handler's signature and determine what parameters it needs."""
        params = list(handler_sig.parameters.values())[1:]  # Skip 'self'
        analysis = {
            "required_params": [],
            "optional_params": [],
            "injectable_params": [],
            "score": 0,
        }

        try:
            type_hints = get_type_hints(handler_sig, include_extras=True)
        except Exception:
            type_hints = {}

        for param in params:
            param_info = {
                "name": param.name,
                "annotation": param.annotation,
                "default": param.default,
                "has_default": param.default != param.empty,
            }

            # Check if parameter is annotated with injection markers
            annotation = type_hints.get(param.name, param.annotation)
            if get_origin(annotation) is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    marker = args[1]
                    if isinstance(marker, Header | Cookie | Query):
                        param_info["injection_marker"] = marker
                        analysis["injectable_params"].append(param_info)

                        # Check if the required data is available in the request
                        if (
                            isinstance(marker, Header)
                            and marker.name in request.headers
                        ):
                            analysis["score"] += 10
                        elif (
                            isinstance(marker, Cookie)
                            and marker.name in request.cookies
                        ):
                            analysis["score"] += 10
                        elif (
                            isinstance(marker, Query)
                            and marker.name in request.query_params
                        ):
                            analysis["score"] += 10
                        elif marker.default is not None:
                            analysis["score"] += 5  # Has default value
                        elif param_info["has_default"]:
                            analysis["score"] += 5  # Parameter has default
                        else:
                            analysis["score"] -= 5  # Required but not available
                        continue

            # Regular parameter handling
            if param_info["has_default"]:
                analysis["optional_params"].append(param_info)
                analysis["score"] += 1
            else:
                analysis["required_params"].append(param_info)
                analysis["score"] -= 2  # Penalize required non-injectable params

        return analysis

    def _calculate_handler_specificity(
        self, handler_info: dict, request: Request, kwargs: dict
    ) -> int:
        """Calculate how specific/targeted this handler is for the current request."""
        sig = handler_info["signature"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'

        try:
            type_hints = get_type_hints(sig, include_extras=True)
        except Exception:
            type_hints = {}

        score = 0
        injectable_params_with_data = 0

        for param in params:
            param_name = param.name
            param_annotation = type_hints.get(param_name, param.annotation)

            # Check if this parameter was actually satisfied from the request data
            if param_name in kwargs:
                if get_origin(param_annotation) is Annotated:
                    args = get_args(param_annotation)
                    if len(args) >= 2:
                        marker = args[1]

                        # Higher score for parameters that got actual data from request
                        if isinstance(marker, Header) and (
                            marker.name in request.headers
                            or marker.name.lower() in request.headers
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual header match
                        elif (
                            isinstance(marker, Cookie)
                            and marker.name in request.cookies
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual cookie match
                        elif (
                            isinstance(marker, Query)
                            and marker.name in request.query_params
                        ):
                            injectable_params_with_data += 1
                            score += 10  # High score for actual query param match
                        elif hasattr(marker, "default") and marker.default is not None:
                            score += 1  # Low score for default values

                elif param.default != param.empty:
                    score += 1  # Low score for parameter defaults
                else:
                    score += 5  # Medium score for container-injected parameters

        # Prefer handlers with more injectable parameters that have actual data
        score += injectable_params_with_data * 5

        return score

    def _can_inject_parameter(self, param_info: dict, request: Request) -> bool:
        """Check if a parameter can be injected from the request."""
        if "injection_marker" not in param_info:
            return False

        marker = param_info["injection_marker"]

        if isinstance(marker, Header):
            return marker.name in request.headers or marker.default is not None
        elif isinstance(marker, Cookie):
            return marker.name in request.cookies or marker.default is not None
        elif isinstance(marker, Query):
            return marker.name in request.query_params or marker.default is not None

        return False

    async def _extract_handler_parameters(
        self,
        handler_info: dict,
        request: Request,
        path_params: dict[str, Any],
        container: Container,
    ) -> dict:
        """Extract and prepare parameters for handler invocation."""
        sig = handler_info["signature"]
        params = list(sig.parameters.values())[1:]  # Skip 'self'
        kwargs = {}

        try:
            type_hints = get_type_hints(sig, include_extras=True)
        except Exception:
            type_hints = {}

        for param in params:
            param_name = param.name
            param_annotation = type_hints.get(param_name, param.annotation)
            value = None
            param_is_required = param.default == param.empty

            # Check for injection annotations - let bevy handle these through container.call()
            # but we need to validate they can be satisfied for compatibility checking
            if get_origin(param_annotation) is Annotated:
                args = get_args(param_annotation)
                if len(args) >= 2:
                    marker = args[1]

                    if isinstance(marker, Header | Cookie | Query):
                        # Let bevy handle injection, but check if required param can be satisfied
                        if isinstance(marker, Header):
                            can_be_satisfied = (
                                marker.name in request.headers
                                or marker.name.lower() in request.headers
                                or marker.default is not None
                            )
                            # Get value for scoring purposes
                            header_value = request.headers.get(
                                marker.name
                            ) or request.headers.get(marker.name.lower())
                            value = (
                                header_value
                                if header_value is not None
                                else marker.default
                            )
                        elif isinstance(marker, Cookie):
                            can_be_satisfied = (
                                marker.name in request.cookies
                                or marker.default is not None
                            )
                            # Get value for scoring purposes
                            value = request.cookies.get(marker.name, marker.default)
                        elif isinstance(marker, Query):
                            can_be_satisfied = (
                                marker.name in request.query_params
                                or marker.default is not None
                            )
                            # Get value for scoring purposes
                            value = request.query_params.get(
                                marker.name, marker.default
                            )

                        # If this is a required parameter that can't be satisfied, handler is incompatible
                        if param_is_required and not can_be_satisfied:
                            from serv.exceptions import HTTPMethodNotAllowedException

                            raise HTTPMethodNotAllowedException(
                                f"Required parameter '{param_name}' cannot be satisfied"
                            )

                        # Include in kwargs for scoring, but bevy will re-inject during actual call
                        if value is not None:
                            kwargs[param_name] = value
                        continue

            # Handle path parameters
            if param_name in path_params:
                kwargs[param_name] = path_params[param_name]
                continue

            # Handle request types
            injection_type = param_annotation
            if get_origin(param_annotation) is Annotated:
                injection_type = get_args(param_annotation)[0]

            if injection_type != param.empty and injection_type is not type(None):
                if hasattr(injection_type, "__mro__") and any(
                    base.__name__ == "Request" for base in injection_type.__mro__
                ):
                    # This is a request type, create it from the incoming request
                    if injection_type.__name__ in [
                        "GetRequest",
                        "PostRequest",
                        "PutRequest",
                        "DeleteRequest",
                        "PatchRequest",
                        "OptionsRequest",
                        "HeadRequest",
                    ]:
                        kwargs[param_name] = injection_type(
                            request.scope, request._receive
                        )
                        continue

                # Try container injection for other types
                try:
                    value = container.get(injection_type)
                    kwargs[param_name] = value
                    continue
                except Exception:
                    pass

            # If we get here and the parameter is required, this handler is incompatible
            if param_is_required:
                from serv.exceptions import HTTPMethodNotAllowedException

                raise HTTPMethodNotAllowedException(
                    f"Required parameter '{param_name}' cannot be satisfied"
                )

            # Optional parameter that couldn't be satisfied - skip it

        return kwargs

    async def _handle_request(
        self, request: Request, container: Container, path_params
    ) -> tuple[Any, dict | None]:
        method = request.method
        handler = None
        handler_info = None
        args_to_pass = []

        # Handle form submissions first
        if self.__form_handlers__.get(method):
            form_data = await request.form()
            for form_type, form_handler_names in self.__form_handlers__[method].items():
                if form_type.matches_form_data(form_data):
                    for name_in_list in form_handler_names:
                        try:
                            parsed_form = await request.form(form_type, data=form_data)
                            handler = getattr(self, name_in_list)
                            handler_info = {"name": name_in_list, "method": handler}
                            args_to_pass = [parsed_form]
                            break
                        except Exception as e:
                            error_response = await container.call(
                                self._error_handler, e, path_params
                            )
                            return error_response, None
                    if handler:
                        break

        # Handle method handlers with signature matching
        if not handler and method in self.__method_handlers__:
            handlers = self.__method_handlers__[method]

            if len(handlers) == 1:
                # Only one handler, use it
                handler_info = handlers[0]
                handler = handler_info["method"]
                try:
                    kwargs_to_pass = await self._extract_handler_parameters(
                        handler_info, request, path_params, container
                    )
                except Exception as e:
                    error_response = await container.call(
                        self._error_handler, e, path_params
                    )
                    return error_response, None
            else:
                # Multiple handlers, find the best match
                compatible_handlers = []

                for handler_info in handlers:
                    try:
                        kwargs_to_pass_temp = await self._extract_handler_parameters(
                            handler_info, request, path_params, container
                        )
                        # Count how many injectable parameters actually got values from the request
                        score = self._calculate_handler_specificity(
                            handler_info, request, kwargs_to_pass_temp
                        )
                        compatible_handlers.append(
                            (score, handler_info, kwargs_to_pass_temp)
                        )
                    except Exception:
                        continue  # Handler is not compatible

                if not compatible_handlers:
                    error_response = await container.call(
                        self._error_handler,
                        HTTPMethodNotAllowedException(
                            f"No compatible handler found for {method} request with provided parameters.",
                            list(
                                self.__method_handlers__.keys()
                                | self.__form_handlers__.keys()
                            ),
                        ),
                        path_params,
                    )
                    return error_response, None

                # Sort by score (highest first) and take the best match
                compatible_handlers.sort(key=lambda x: x[0], reverse=True)
                score, selected_handler_info, kwargs_to_pass = compatible_handlers[0]
                handler = selected_handler_info["method"]
                handler_info = selected_handler_info

        if not handler:
            error_response = await container.call(
                self._error_handler,
                HTTPMethodNotAllowedException(
                    f"{type(self).__name__} does not support {method} or a matching form handler for provided data.",
                    list(
                        self.__method_handlers__.keys() | self.__form_handlers__.keys()
                    ),
                ),
                path_params,
            )
            return error_response, None

        try:
            # Call handler with extracted parameters
            if "kwargs_to_pass" in locals() and kwargs_to_pass:
                handler_output_data = await container.call(
                    handler, self, **kwargs_to_pass
                )
            elif "args_to_pass" in locals() and args_to_pass:
                # For form handlers, call directly to avoid container injection conflicts
                handler_output_data = await handler(*args_to_pass)
            else:
                handler_output_data = await container.call(handler, self)

            handler_name = handler_info.get("name") if handler_info else None
            if handler_name and handler_name in self.__annotated_response_wrappers__:
                wrapper_class = self.__annotated_response_wrappers__[handler_name]
                if isinstance(handler_output_data, tuple):
                    response = wrapper_class(*handler_output_data)
                else:
                    response = wrapper_class(handler_output_data)
            elif isinstance(handler_output_data, Response):
                response = handler_output_data
            else:
                # Check if this handler should have had an annotated response wrapper
                should_have_wrapper = False
                wrapper_info = ""

                if handler_name:
                    # Check if the handler method has an annotated return type
                    try:
                        if hasattr(self, handler_name):
                            handler_method = getattr(self, handler_name)
                            from typing import get_args, get_origin, get_type_hints

                            type_hints = get_type_hints(
                                handler_method, include_extras=True
                            )
                            return_annotation = type_hints.get("return")

                            if (
                                return_annotation
                                and get_origin(return_annotation) is Annotated
                            ):
                                args = get_args(return_annotation)
                                if (
                                    len(args) == 2
                                    and isinstance(args[1], type)
                                    and issubclass(args[1], Response)
                                ):
                                    should_have_wrapper = True
                                    wrapper_info = (
                                        f" (should be wrapped in {args[1].__name__})"
                                    )
                    except Exception:
                        pass

                # Get detailed information about the handler for better error reporting
                handler_class = type(self).__name__
                handler_module = type(self).__module__

                # Try to get the file and line number of the handler method
                import inspect

                handler_file = "unknown"
                handler_line = "unknown"
                try:
                    handler_source = inspect.getsourcefile(handler)
                    handler_lines = inspect.getsourcelines(handler)
                    if handler_source:
                        handler_file = handler_source
                    if handler_lines:
                        handler_line = handler_lines[
                            1
                        ]  # Line number where the function starts
                except Exception:
                    pass

                # Create a detailed error message
                if should_have_wrapper:
                    error_msg = (
                        f"Route handler has annotated response type but wrapper was not applied:\n"
                        f"  Handler: {handler_class}.{handler_name}()\n"
                        f"  Module: {handler_module}\n"
                        f"  File: {handler_file}\n"
                        f"  Line: {handler_line}\n"
                        f"  Route: {request.method} '{request.path}'\n"
                        f"  Returned: {type(handler_output_data).__name__!r} ({repr(handler_output_data)[:100]}{'...' if len(repr(handler_output_data)) > 100 else ''})\n"
                        f"  Expected wrapper: {wrapper_info}\n"
                        f"  Issue: Annotated response wrapper was not applied (this is a framework bug)\n"
                        f"  Debug info: handler_name='{handler_name}', in_wrappers={handler_name in self.__annotated_response_wrappers__ if handler_name else False}"
                    )
                else:
                    error_msg = (
                        f"Route handler returned wrong type:\n"
                        f"  Handler: {handler_class}.{handler_name}()\n"
                        f"  Module: {handler_module}\n"
                        f"  File: {handler_file}\n"
                        f"  Line: {handler_line}\n"
                        f"  Route: {request.method} '{request.path}'\n"
                        f"  Returned: {type(handler_output_data).__name__!r} ({repr(handler_output_data)[:100]}{'...' if len(repr(handler_output_data)) > 100 else ''})\n"
                        f"  Expected: Response instance or use an Annotated response type"
                    )

                raise TypeError(error_msg)

            response.set_created_by(self.extension)
            return response, handler_info

        except Exception as e:
            error_response = await container.call(
                self._error_handler, e, container, path_params
            )
            return error_response, handler_info

    @injectable
    async def _error_handler(
        self,
        exception: Exception,
        container: Inject[Container],
        path_params: dict[str, Any] | None = None,
    ) -> Response:
        path_params = path_params or {}
        for error_type, handler_name in self.__error_handlers__.items():
            if isinstance(exception, error_type):
                try:
                    handler = getattr(self, handler_name)
                    return await container.call(handler, exception, **path_params)
                except Exception as e:
                    e.__cause__ = exception
                    return await container.call(
                        self._error_handler, e, container, path_params
                    )

        raise exception